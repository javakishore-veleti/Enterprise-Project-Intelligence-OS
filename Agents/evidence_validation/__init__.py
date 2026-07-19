"""Evidence Validation processor (LLM).

Reviews each candidate finding against the deterministic evidence and drops the
ones the evidence does not support, adjusting confidence on the survivors. Uses
a single LangChain structured-output call to Claude (the review *pipeline* that
sequences processors is the LangGraph graph, in RiskAnalytics-API).
"""
from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from agent_core import FindingProcessor, ReviewContext, RiskFinding
from evidence_validation.prompts import SYSTEM_PROMPT, build_user_prompt

AGENT_KEY = "evidence_validation"
DEFAULT_MODEL = "claude-opus-4-8"


class _Verdict(BaseModel):
    index: int
    supported: bool
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    note: str = ""


class _Validation(BaseModel):
    verdicts: list[_Verdict] = Field(default_factory=list)


class EvidenceValidationProcessor(FindingProcessor):
    agent_key = AGENT_KEY

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._llm = ChatAnthropic(model=model, max_tokens=1500, timeout=60).with_structured_output(
            _Validation
        )

    def process(self, context: ReviewContext) -> list[RiskFinding]:
        if not context.findings:
            return []
        result: _Validation = self._llm.invoke(
            [("system", SYSTEM_PROMPT), ("human", build_user_prompt(context))]
        )
        verdict_by_index = {v.index: v for v in result.verdicts}
        kept: list[RiskFinding] = []
        for i, f in enumerate(context.findings):
            v = verdict_by_index.get(i)
            if v is None:
                kept.append(f)  # no verdict -> keep unchanged (fail open)
                continue
            if not v.supported:
                continue  # drop unsupported
            kept.append(f.model_copy(update={
                "confidence": v.adjusted_confidence,
                "meta": {**f.meta, "validated": True, "validation_note": v.note},
            }))
        return kept


def build(model: str = DEFAULT_MODEL, framework: str = "langgraph") -> EvidenceValidationProcessor:
    return EvidenceValidationProcessor(model=model)
