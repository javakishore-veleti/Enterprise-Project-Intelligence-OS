"""Stub adapters for the non-default frameworks (backlog-health agent)."""
from __future__ import annotations

from agent_core import EvidencePackage, RiskFinding
from backlog_health.contract import BacklogHealthAgent


class _NotYetImplementedAgent(BacklogHealthAgent):
    framework_name = "unknown"

    def __init__(self, model: str) -> None:
        self._model = model

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        raise NotImplementedError(
            f"The '{self.framework_name}' adapter for backlog_health is not implemented yet."
        )


class CrewAIBacklogHealthAgent(_NotYetImplementedAgent):
    framework_name = "crewai"


class OpenAIAgentsBacklogHealthAgent(_NotYetImplementedAgent):
    framework_name = "openai_agents"


class StrandsBacklogHealthAgent(_NotYetImplementedAgent):
    framework_name = "strands"


class GoogleADKBacklogHealthAgent(_NotYetImplementedAgent):
    framework_name = "google_adk"


class MSAgentFrameworkBacklogHealthAgent(_NotYetImplementedAgent):
    framework_name = "ms_agent_framework"
