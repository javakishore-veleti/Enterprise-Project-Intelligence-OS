"""Project Risk Manager — resolves specialist agents for an analysis run.

For this slice the manager maps each supported agent key to its framework
adapter (via the agent's own registry), honoring the framework toggle from
Admin-API. The individual agent's orchestration (a LangGraph graph) lives in the
agent package. When more than one agent is implemented, this module grows into
the LangGraph coordinator graph that fans out to specialists, correlates, and
deduplicates their findings.
"""
from __future__ import annotations

from agent_core import RiskAgent

# agent_key -> builder(framework, model) -> RiskAgent
_BUILDERS: dict[str, object] = {}


def _register_builders() -> None:
    if _BUILDERS:
        return
    from schedule_risk import build_agent as build_schedule_risk

    _BUILDERS["schedule_risk"] = build_schedule_risk


def build_agent(agent_key: str, framework: str, model: str) -> RiskAgent | None:
    """Return an agent for (key, framework, model), or None if not implemented."""
    _register_builders()
    builder = _BUILDERS.get(agent_key)
    if builder is None:
        return None
    return builder(framework, model)


def supported_agents() -> list[str]:
    _register_builders()
    return sorted(_BUILDERS)
