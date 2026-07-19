"""Framework toggle: build a quality-risk agent for the configured framework."""
from __future__ import annotations

from quality_risk.contract import QualityRiskAgent

_LANGGRAPH = "langgraph"
_STUBS = {
    "crewai": "CrewAIQualityRiskAgent",
    "openai_agents": "OpenAIAgentsQualityRiskAgent",
    "strands": "StrandsQualityRiskAgent",
    "google_adk": "GoogleADKQualityRiskAgent",
    "ms_agent_framework": "MSAgentFrameworkQualityRiskAgent",
}

SUPPORTED_FRAMEWORKS = (_LANGGRAPH, *_STUBS.keys())


def build_agent(framework: str, model: str) -> QualityRiskAgent:
    framework = (framework or _LANGGRAPH).lower()
    if framework == _LANGGRAPH:
        from quality_risk.adapters.langgraph_adapter import LangGraphQualityRiskAgent

        return LangGraphQualityRiskAgent(model=model)
    if framework in _STUBS:
        from quality_risk.adapters import other_frameworks

        return getattr(other_frameworks, _STUBS[framework])(model=model)
    raise ValueError(
        f"unknown framework '{framework}'. Supported: {', '.join(SUPPORTED_FRAMEWORKS)}"
    )
