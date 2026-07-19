"""Stub adapters for the non-default frameworks.

These document the extension points for the multi-framework showcase. Each will
implement the same ``ScheduleRiskAgent`` port with the same prompts/tools, only
differing in orchestration. Implement one to prove the seam before the rest.
"""
from __future__ import annotations

from agent_core import EvidencePackage, RiskFinding
from schedule_risk.contract import ScheduleRiskAgent


class _NotYetImplementedAgent(ScheduleRiskAgent):
    framework_name = "unknown"

    def __init__(self, model: str) -> None:
        self._model = model

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        raise NotImplementedError(
            f"The '{self.framework_name}' adapter for schedule_risk is not implemented yet. "
            "Set this agent's framework to 'langgraph' in Admin-API, or implement this adapter."
        )


class CrewAIScheduleRiskAgent(_NotYetImplementedAgent):
    framework_name = "crewai"


class OpenAIAgentsScheduleRiskAgent(_NotYetImplementedAgent):
    framework_name = "openai_agents"


class StrandsScheduleRiskAgent(_NotYetImplementedAgent):
    framework_name = "strands"


class GoogleADKScheduleRiskAgent(_NotYetImplementedAgent):
    framework_name = "google_adk"


class MSAgentFrameworkScheduleRiskAgent(_NotYetImplementedAgent):
    framework_name = "ms_agent_framework"
