"""Stub adapters for the non-default frameworks (quality-risk agent)."""
from __future__ import annotations

from agent_core import EvidencePackage, RiskFinding
from quality_risk.contract import QualityRiskAgent


class _NotYetImplementedAgent(QualityRiskAgent):
    framework_name = "unknown"

    def __init__(self, model: str) -> None:
        self._model = model

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        raise NotImplementedError(
            f"The '{self.framework_name}' adapter for quality_risk is not implemented yet."
        )


class CrewAIQualityRiskAgent(_NotYetImplementedAgent):
    framework_name = "crewai"


class OpenAIAgentsQualityRiskAgent(_NotYetImplementedAgent):
    framework_name = "openai_agents"


class StrandsQualityRiskAgent(_NotYetImplementedAgent):
    framework_name = "strands"


class GoogleADKQualityRiskAgent(_NotYetImplementedAgent):
    framework_name = "google_adk"


class MSAgentFrameworkQualityRiskAgent(_NotYetImplementedAgent):
    framework_name = "ms_agent_framework"
