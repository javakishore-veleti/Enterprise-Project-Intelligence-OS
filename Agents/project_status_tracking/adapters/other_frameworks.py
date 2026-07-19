"""Stub adapters for the non-default frameworks (project-status-tracking agent)."""
from __future__ import annotations

from agent_core import EvidencePackage, RiskFinding
from project_status_tracking.contract import ProjectStatusTrackingAgent


class _NotYetImplementedAgent(ProjectStatusTrackingAgent):
    framework_name = "unknown"

    def __init__(self, model: str) -> None:
        self._model = model

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        raise NotImplementedError(
            f"The '{self.framework_name}' adapter for project_status_tracking is not implemented yet."
        )


class CrewAIProjectStatusTrackingAgent(_NotYetImplementedAgent):
    framework_name = "crewai"


class OpenAIAgentsProjectStatusTrackingAgent(_NotYetImplementedAgent):
    framework_name = "openai_agents"


class StrandsProjectStatusTrackingAgent(_NotYetImplementedAgent):
    framework_name = "strands"


class GoogleADKProjectStatusTrackingAgent(_NotYetImplementedAgent):
    framework_name = "google_adk"


class MSAgentFrameworkProjectStatusTrackingAgent(_NotYetImplementedAgent):
    framework_name = "ms_agent_framework"
