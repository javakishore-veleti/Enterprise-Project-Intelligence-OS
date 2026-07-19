"""Framework toggle: build a resource-risk agent for the configured framework."""
from __future__ import annotations

from resource_risk.contract import ResourceRiskAgent

_LANGGRAPH = "langgraph"
_STUBS = {
    "crewai": "CrewAIResourceRiskAgent",
    "openai_agents": "OpenAIAgentsResourceRiskAgent",
    "strands": "StrandsResourceRiskAgent",
    "google_adk": "GoogleADKResourceRiskAgent",
    "ms_agent_framework": "MSAgentFrameworkResourceRiskAgent",
}

SUPPORTED_FRAMEWORKS = (_LANGGRAPH, *_STUBS.keys())


def build_agent(framework: str, model: str) -> ResourceRiskAgent:
    framework = (framework or _LANGGRAPH).lower()
    if framework == _LANGGRAPH:
        from resource_risk.adapters.langgraph_adapter import LangGraphResourceRiskAgent

        return LangGraphResourceRiskAgent(model=model)
    if framework in _STUBS:
        from resource_risk.adapters import other_frameworks

        return getattr(other_frameworks, _STUBS[framework])(model=model)
    raise ValueError(
        f"unknown framework '{framework}'. Supported: {', '.join(SUPPORTED_FRAMEWORKS)}"
    )
