"""Framework toggle: build a project-status-tracking agent for the configured framework."""
from __future__ import annotations

from project_status_tracking.contract import ProjectStatusTrackingAgent

_LANGGRAPH = "langgraph"
_STUBS = {
    "crewai": "CrewAIProjectStatusTrackingAgent",
    "openai_agents": "OpenAIAgentsProjectStatusTrackingAgent",
    "strands": "StrandsProjectStatusTrackingAgent",
    "google_adk": "GoogleADKProjectStatusTrackingAgent",
    "ms_agent_framework": "MSAgentFrameworkProjectStatusTrackingAgent",
}

SUPPORTED_FRAMEWORKS = (_LANGGRAPH, *_STUBS.keys())


def build_agent(framework: str, model: str) -> ProjectStatusTrackingAgent:
    framework = (framework or _LANGGRAPH).lower()
    if framework == _LANGGRAPH:
        from project_status_tracking.adapters.langgraph_adapter import LangGraphProjectStatusTrackingAgent

        return LangGraphProjectStatusTrackingAgent(model=model)
    if framework in _STUBS:
        from project_status_tracking.adapters import other_frameworks

        return getattr(other_frameworks, _STUBS[framework])(model=model)
    raise ValueError(
        f"unknown framework '{framework}'. Supported: {', '.join(SUPPORTED_FRAMEWORKS)}"
    )
