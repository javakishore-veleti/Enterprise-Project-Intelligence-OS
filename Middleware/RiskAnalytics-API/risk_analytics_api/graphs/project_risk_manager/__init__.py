"""Project Risk Manager — a LangGraph fan-out over specialist agents.

The manager is a LangGraph ``StateGraph`` that dispatches one worker per agent
spec (map) and merges their findings (reduce). Each worker builds its agent via
the framework toggle and runs it; a worker that fails records a per-agent error
instead of aborting the whole run, so one failing specialist does not lose the
others' findings. Each agent's own orchestration (its LangGraph graph, or a
different framework) lives in the agent package.
"""
from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Callable, TypedDict

from agent_core import EvidencePackage, RiskAgent, RiskFinding
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

# (agent_key, framework, model) -> RiskAgent, or None if the agent_key is not implemented.
AgentFactory = Callable[[str, str, str], "RiskAgent | None"]

# ---- Agent registry: which agent keys are implemented, and how to build them ----

_BUILDERS: dict[str, Callable[[str, str], RiskAgent]] = {}


def _register_builders() -> None:
    if _BUILDERS:
        return
    from schedule_risk import build_agent as build_schedule_risk
    from quality_risk import build_agent as build_quality_risk

    _BUILDERS["schedule_risk"] = build_schedule_risk
    _BUILDERS["quality_risk"] = build_quality_risk


def build_agent(agent_key: str, framework: str, model: str) -> RiskAgent | None:
    """Default agent factory: return an agent for (key, framework, model) or None."""
    _register_builders()
    builder = _BUILDERS.get(agent_key)
    if builder is None:
        return None
    return builder(framework, model)


def supported_agents() -> list[str]:
    _register_builders()
    return sorted(_BUILDERS)


# ---- The manager graph ----

AgentSpec = tuple[str, str, str]  # (agent_key, framework, model)


@dataclass
class ManagerResult:
    findings: list[RiskFinding] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


class _ManagerState(TypedDict, total=False):
    evidence: EvidencePackage
    specs: list[AgentSpec]
    findings: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]


class _WorkerState(TypedDict):
    evidence: EvidencePackage
    spec: AgentSpec


class ProjectRiskManager:
    """Fan out an analysis across specialist agents using LangGraph."""

    def __init__(self, agent_factory: AgentFactory) -> None:
        self._factory = agent_factory
        self._graph = self._build()

    def _build(self):
        graph = StateGraph(_ManagerState)
        graph.add_node("run_agent", self._run_agent)
        graph.add_conditional_edges(START, self._dispatch, ["run_agent"])
        graph.add_edge("run_agent", END)
        return graph.compile()

    def _dispatch(self, state: _ManagerState) -> list[Send]:
        return [
            Send("run_agent", {"evidence": state["evidence"], "spec": spec})
            for spec in state.get("specs", [])
        ]

    def _run_agent(self, state: _WorkerState) -> dict:
        agent_key, framework, model = state["spec"]
        try:
            agent = self._factory(agent_key, framework, model)
            if agent is None:
                return {"findings": [], "errors": []}
            return {"findings": list(agent.analyze(state["evidence"])), "errors": []}
        except Exception as exc:  # one specialist failing must not abort the rest
            return {"findings": [], "errors": [{"agent_key": agent_key, "error": str(exc)}]}

    def run(self, evidence: EvidencePackage, specs: list[AgentSpec]) -> ManagerResult:
        if not specs:
            return ManagerResult()
        out = self._graph.invoke(
            {"evidence": evidence, "specs": specs, "findings": [], "errors": []}
        )
        return ManagerResult(findings=out.get("findings", []), errors=out.get("errors", []))
