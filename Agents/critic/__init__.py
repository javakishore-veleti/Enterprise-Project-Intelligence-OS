"""Critic processor (LLM).

Adversarially reviews the finding set: keeps, weakens (lowers confidence), or
drops each finding. Runs late in the review pipeline as the final quality gate.
"""
from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from agent_core import FindingProcessor, ReviewContext, RiskFinding
from critic.prompts import SYSTEM_PROMPT, build_user_prompt

AGENT_KEY = "critic"
DEFAULT_MODEL = "claude-opus-4-8"


class _Verdict(BaseModel):
    index: int
    verdict: str = Field(description="one of: keep, weaken, drop")
    critique: str = ""


class _Critique(BaseModel):
    verdicts: list[_Verdict] = Field(default_factory=list)


class CriticProcessor(FindingProcessor):
    agent_key = AGENT_KEY

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._llm = ChatAnthropic(model=model, max_tokens=1500, timeout=60).with_structured_output(
            _Critique
        )

    def process(self, context: ReviewContext) -> list[RiskFinding]:
        if not context.findings:
            return []
        result: _Critique = self._llm.invoke(
            [("system", SYSTEM_PROMPT), ("human", build_user_prompt(context))]
        )
        by_index = {v.index: v for v in result.verdicts}
        kept: list[RiskFinding] = []
        for i, f in enumerate(context.findings):
            v = by_index.get(i)
            if v is None:
                kept.append(f)
                continue
            verdict = (v.verdict or "keep").lower()
            if verdict == "drop":
                continue
            meta = {**f.meta, "critic_verdict": verdict, "critique": v.critique}
            if verdict == "weaken":
                kept.append(f.model_copy(update={
                    "confidence": round(max(0.0, f.confidence * 0.7), 2), "meta": meta,
                }))
            else:
                kept.append(f.model_copy(update={"meta": meta}))
        return kept


def build(model: str = DEFAULT_MODEL, framework: str = "langgraph") -> CriticProcessor:
    return CriticProcessor(model=model)
