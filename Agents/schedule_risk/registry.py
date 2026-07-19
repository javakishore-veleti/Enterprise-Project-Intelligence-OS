"""Framework toggle: build a schedule-risk agent for the configured framework.

The framework string comes from Admin-API agent configuration. LangGraph is the
implemented default; the others raise a clear NotImplementedError until built.
Importing a framework's adapter is lazy so unused (and possibly heavy) SDKs are
never imported.
"""
from __future__ import annotations

from schedule_risk.contract import ScheduleRiskAgent

_LANGGRAPH = "langgraph"
_OPENAI_AGENTS = "openai_agents"
# Frameworks still awaiting a real adapter (raise NotImplementedError on analyze).
_STUBS = {
    "crewai": "CrewAIScheduleRiskAgent",
    "strands": "StrandsScheduleRiskAgent",
    "google_adk": "GoogleADKScheduleRiskAgent",
    "ms_agent_framework": "MSAgentFrameworkScheduleRiskAgent",
}

SUPPORTED_FRAMEWORKS = (_LANGGRAPH, _OPENAI_AGENTS, *_STUBS.keys())

# Frameworks with a real, runnable adapter (the rest are documented stubs).
IMPLEMENTED_FRAMEWORKS = (_LANGGRAPH, _OPENAI_AGENTS)


def build_agent(framework: str, model: str) -> ScheduleRiskAgent:
    framework = (framework or _LANGGRAPH).lower()
    if framework == _LANGGRAPH:
        from schedule_risk.adapters.langgraph_adapter import LangGraphScheduleRiskAgent

        return LangGraphScheduleRiskAgent(model=model)
    if framework == _OPENAI_AGENTS:
        from schedule_risk.adapters.openai_agents_adapter import (
            OpenAIAgentsScheduleRiskAgent,
        )

        return OpenAIAgentsScheduleRiskAgent(model=model)
    if framework in _STUBS:
        from schedule_risk.adapters import other_frameworks

        return getattr(other_frameworks, _STUBS[framework])(model=model)
    raise ValueError(
        f"unknown framework '{framework}'. Supported: {', '.join(SUPPORTED_FRAMEWORKS)}"
    )
