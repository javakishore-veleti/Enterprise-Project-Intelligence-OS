"""Stub adapters for the non-default frameworks (dependency-risk agent)."""
from __future__ import annotations

from agent_core import EvidencePackage, RiskFinding
from dependency_risk.contract import DependencyRiskAgent


class _NotYetImplementedAgent(DependencyRiskAgent):
    framework_name = "unknown"

    def __init__(self, model: str) -> None:
        self._model = model

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        raise NotImplementedError(
            f"The '{self.framework_name}' adapter for dependency_risk is not implemented yet."
        )


class CrewAIDependencyRiskAgent(_NotYetImplementedAgent):
    framework_name = "crewai"


class OpenAIAgentsDependencyRiskAgent(_NotYetImplementedAgent):
    framework_name = "openai_agents"


class StrandsDependencyRiskAgent(_NotYetImplementedAgent):
    framework_name = "strands"


class GoogleADKDependencyRiskAgent(_NotYetImplementedAgent):
    framework_name = "google_adk"


class MSAgentFrameworkDependencyRiskAgent(_NotYetImplementedAgent):
    framework_name = "ms_agent_framework"
