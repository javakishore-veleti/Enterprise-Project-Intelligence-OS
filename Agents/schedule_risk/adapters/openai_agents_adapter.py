"""OpenAI Agents SDK adapter for the schedule-risk agent.

Proves the framework seam: the SAME port, prompts, and deterministic scoring as
the LangGraph adapter, but orchestrated by the OpenAI Agents SDK. The model is
held constant — routed to Claude via LiteLLM (`anthropic/<model>`) — so a
comparison measures orchestration, not the model.

Requires the optional extra:  pip install "epi-agents[frameworks-openai]"
The API key is read from ANTHROPIC_API_KEY at call time (never stored).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from agent_core import (
    EvidencePackage,
    RiskCategory,
    RiskFinding,
    risk_score,
    severity_from_score,
)
from schedule_risk.contract import AGENT_KEY, ScheduleRiskAgent
from schedule_risk.prompts import SYSTEM_PROMPT, build_user_prompt


class _LLMFinding(BaseModel):
    probability: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    assumptions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class _Assessment(BaseModel):
    findings: list[_LLMFinding] = Field(default_factory=list)


class OpenAIAgentsScheduleRiskAgent(ScheduleRiskAgent):
    def __init__(self, model: str = "claude-opus-4-8") -> None:
        # Imported lazily so the SDK is only required when this framework is selected.
        from agents import Agent
        from agents.extensions.models.litellm_model import LitellmModel

        self._model = model
        self._Runner = __import__("agents", fromlist=["Runner"]).Runner
        self._agent = Agent(
            name="schedule_risk",
            instructions=SYSTEM_PROMPT,
            model=LitellmModel(
                model=f"anthropic/{model}",
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
            ),
            output_type=_Assessment,
        )

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        result = self._Runner.run_sync(self._agent, build_user_prompt(evidence))
        assessment: _Assessment = result.final_output
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
        return findings
