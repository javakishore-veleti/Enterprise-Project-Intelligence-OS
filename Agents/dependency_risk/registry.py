"""Framework toggle: build a dependency-risk agent for the configured framework."""
from __future__ import annotations

from dependency_risk.contract import DependencyRiskAgent

_LANGGRAPH = "langgraph"
_STUBS = {
    "crewai": "CrewAIDependencyRiskAgent",
    "openai_agents": "OpenAIAgentsDependencyRiskAgent",
    "strands": "StrandsDependencyRiskAgent",
    "google_adk": "GoogleADKDependencyRiskAgent",
    "ms_agent_framework": "MSAgentFrameworkDependencyRiskAgent",
}

SUPPORTED_FRAMEWORKS = (_LANGGRAPH, *_STUBS.keys())


def build_agent(framework: str, model: str) -> DependencyRiskAgent:
    framework = (framework or _LANGGRAPH).lower()
    if framework == _LANGGRAPH:
        from dependency_risk.adapters.langgraph_adapter import LangGraphDependencyRiskAgent

        return LangGraphDependencyRiskAgent(model=model)
    if framework in _STUBS:
        from dependency_risk.adapters import other_frameworks

        return getattr(other_frameworks, _STUBS[framework])(model=model)
    raise ValueError(
        f"unknown framework '{framework}'. Supported: {', '.join(SUPPORTED_FRAMEWORKS)}"
    )
