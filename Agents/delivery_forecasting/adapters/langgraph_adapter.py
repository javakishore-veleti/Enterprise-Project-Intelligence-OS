"""LangGraph adapter for the delivery-forecasting agent (the default framework)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agent_core import (
    EvidencePackage,
    RiskCategory,
    RiskFinding,
    risk_score,
    severity_from_score,
)
from delivery_forecasting.contract import AGENT_KEY, DeliveryForecastingAgent
from delivery_forecasting.prompts import SYSTEM_PROMPT, build_user_prompt

DEFAULT_MODEL = "claude-opus-4-8"


class _LLMFinding(BaseModel):
    probability: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    assumptions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class _Assessment(BaseModel):
    findings: list[_LLMFinding] = Field(default_factory=list)


class _State(TypedDict, total=False):
    evidence: EvidencePackage
    findings: list[RiskFinding]


class LangGraphDeliveryForecastingAgent(DeliveryForecastingAgent):
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
            [("system", SYSTEM_PROMPT), ("human", build_user_prompt(evidence))]
        )
        now = datetime.now(timezone.utc)
        findings: list[RiskFinding] = []
        for f in assessment.findings:
            score = risk_score(f.probability, f.impact)
            findings.append(
                RiskFinding(
                    risk_category=RiskCategory.RELEASE_READINESS,
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
