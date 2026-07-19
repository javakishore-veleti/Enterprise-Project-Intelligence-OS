"""Framework toggle: build a backlog-health agent for the configured framework."""
from __future__ import annotations

from backlog_health.contract import BacklogHealthAgent

_LANGGRAPH = "langgraph"
_STUBS = {
    "crewai": "CrewAIBacklogHealthAgent",
    "openai_agents": "OpenAIAgentsBacklogHealthAgent",
    "strands": "StrandsBacklogHealthAgent",
    "google_adk": "GoogleADKBacklogHealthAgent",
    "ms_agent_framework": "MSAgentFrameworkBacklogHealthAgent",
}

SUPPORTED_FRAMEWORKS = (_LANGGRAPH, *_STUBS.keys())


def build_agent(framework: str, model: str) -> BacklogHealthAgent:
    framework = (framework or _LANGGRAPH).lower()
    if framework == _LANGGRAPH:
        from backlog_health.adapters.langgraph_adapter import LangGraphBacklogHealthAgent

        return LangGraphBacklogHealthAgent(model=model)
    if framework in _STUBS:
        from backlog_health.adapters import other_frameworks

        return getattr(other_frameworks, _STUBS[framework])(model=model)
    raise ValueError(
        f"unknown framework '{framework}'. Supported: {', '.join(SUPPORTED_FRAMEWORKS)}"
    )
