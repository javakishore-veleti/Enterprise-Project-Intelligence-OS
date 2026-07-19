"""LangGraph adapter for the schedule-risk agent (the default framework).

Orchestration: a LangGraph ``StateGraph`` whose single node performs one
LangChain structured-output call to Claude. Probability/impact/explanation come
from the model; score and severity are computed deterministically from the
shared tools so every framework adapter scores identically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agent_core import EvidencePackage, RiskCategory, RiskFinding
from schedule_risk.contract import AGENT_KEY, ScheduleRiskAgent
from schedule_risk.prompts import SYSTEM_PROMPT, build_user_prompt
from schedule_risk.tools import risk_score, severity_from_score

DEFAULT_MODEL = "claude-opus-4-8"


class _LLMFinding(BaseModel):
    """Model-facing schema — only the fields the LLM should judge."""

    probability: float = Field(ge=0.0, le=1.0, description="Likelihood the schedule risk materializes.")
    impact: float = Field(ge=0.0, le=1.0, description="Delivery impact if it does.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence given the evidence strength.")
    explanation: str
    assumptions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class _Assessment(BaseModel):
    findings: list[_LLMFinding] = Field(default_factory=list)


class _State(TypedDict, total=False):
    evidence: EvidencePackage
    findings: list[RiskFinding]


class LangGraphScheduleRiskAgent(ScheduleRiskAgent):
    def __init__(self, model: str = DEFAULT_MODEL, *, max_tokens: int = 1500, timeout: int = 60) -> None:
        self._model = model
        self._llm = ChatAnthropic(
            model=model, max_tokens=max_tokens, timeout=timeout
        ).with_structured_output(_Assessment)
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(_State)
        graph.add_node("assess", self._assess)
        graph.add_edge(START, "assess")
        graph.add_edge("assess", END)
        return graph.compile()

    def _assess(self, state: _State) -> _State:
        evidence = state["evidence"]
        assessment: _Assessment = self._llm.invoke(
            [
                ("system", SYSTEM_PROMPT),
                ("human", build_user_prompt(evidence)),
            ]
        )
        now = datetime.now(timezone.utc)
        findings: list[RiskFinding] = []
        for f in assessment.findings:
            score = risk_score(f.probability, f.impact)
            findings.append(
                RiskFinding(
                    risk_category=RiskCategory.SCHEDULE,
                    probability=f.probability,
                    impact=f.impact,
                    severity=severity_from_score(score),
                    score=score,
                    confidence=f.confidence,
                    explanation=f.explanation,
                    assumptions=f.assumptions,
                    recommended_actions=f.recommended_actions,
                    affected=[evidence.project_key],
                    source_agent=AGENT_KEY,
                    analysis_timestamp=now,
                )
            )
        return {"findings": findings}

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        result = self._graph.invoke({"evidence": evidence})
        return result.get("findings", [])
