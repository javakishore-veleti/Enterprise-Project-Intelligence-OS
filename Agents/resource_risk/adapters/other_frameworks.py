"""Stub adapters for the non-default frameworks (resource-risk agent)."""
from __future__ import annotations

from agent_core import EvidencePackage, RiskFinding
from resource_risk.contract import ResourceRiskAgent


class _NotYetImplementedAgent(ResourceRiskAgent):
    framework_name = "unknown"

    def __init__(self, model: str) -> None:
        self._model = model

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        raise NotImplementedError(
            f"The '{self.framework_name}' adapter for resource_risk is not implemented yet."
        )


class CrewAIResourceRiskAgent(_NotYetImplementedAgent):
    framework_name = "crewai"


class OpenAIAgentsResourceRiskAgent(_NotYetImplementedAgent):
    framework_name = "openai_agents"


class StrandsResourceRiskAgent(_NotYetImplementedAgent):
    framework_name = "strands"


class GoogleADKResourceRiskAgent(_NotYetImplementedAgent):
    framework_name = "google_adk"


class MSAgentFrameworkResourceRiskAgent(_NotYetImplementedAgent):
    framework_name = "ms_agent_framework"
