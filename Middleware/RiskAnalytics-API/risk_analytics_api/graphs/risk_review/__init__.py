"""Risk Review — a sequential LangGraph pipeline over detector findings.

After the detector fan-out (``project_risk_manager``) produces raw findings, this
pipeline refines them and reports on them:

    validate -> dedup -> correlate -> score -> critic -> report

Processors (findings -> findings) run as ordered LangGraph nodes; the final
`report` node runs every enabled reporter (findings -> RiskReport). Which agents
run — and their model — comes from Admin-API config, so a disabled review agent
is simply skipped. Deterministic processors (dedup/correlate/score) use no LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypedDict

from agent_core import FindingProcessor, Reporter, ReviewContext, RiskFinding, RiskReport
from langgraph.graph import END, START, StateGraph

# Processor stages, in pipeline order, and the reporter agents.
PROCESSOR_ORDER = [
    "evidence_validation",
    "risk_deduplication",
    "risk_correlation",
    "risk_scoring",
    "critic",
]
REPORTER_AGENTS = ["mitigation_planning", "project_reporting", "executive_reporting"]

# agent_key -> (enabled, model, framework) | None
ConfigLookup = Callable[[str], "tuple[bool, str, str] | None"]


def _builders() -> dict[str, Callable]:
    from critic import build as b_critic
    from evidence_validation import build as b_validation
    from executive_reporting import build as b_exec
    from mitigation_planning import build as b_mitigation
    from project_reporting import build as b_project
    from risk_correlation import build as b_correlation
    from risk_deduplication import build as b_dedup
    from risk_scoring import build as b_scoring

    return {
        "evidence_validation": b_validation,
        "risk_deduplication": b_dedup,
        "risk_correlation": b_correlation,
        "risk_scoring": b_scoring,
        "critic": b_critic,
        "mitigation_planning": b_mitigation,
        "project_reporting": b_project,
        "executive_reporting": b_exec,
    }


@dataclass
class ReviewResult:
    findings: list[RiskFinding] = field(default_factory=list)
    reports: list[RiskReport] = field(default_factory=list)


class _State(TypedDict, total=False):
    ctx: ReviewContext
    reports: list[RiskReport]


class ProjectRiskReview:
    """Compiles the ordered processors + reporters into a LangGraph pipeline."""

    def __init__(self, processors: list[tuple[str, FindingProcessor]], reporters: list[Reporter]) -> None:
        self._processors = processors
        self._reporters = reporters
        self._graph = self._build()

    def _build(self):
        graph = StateGraph(_State)
        prev = START
        for agent_key, proc in self._processors:
            node = f"proc_{agent_key}"
            graph.add_node(node, self._proc_node(proc))
            graph.add_edge(prev, node)
            prev = node
        graph.add_node("report", self._report_node)
        graph.add_edge(prev, "report")
        graph.add_edge("report", END)
        return graph.compile()

    def _proc_node(self, proc: FindingProcessor):
        def node(state: _State) -> _State:
            ctx = state["ctx"]
            return {"ctx": ctx.with_findings(proc.process(ctx))}
        return node

    def _report_node(self, state: _State) -> _State:
        ctx = state["ctx"]
        return {"reports": [r.report(ctx) for r in self._reporters]}

    def run(self, context: ReviewContext) -> ReviewResult:
        out = self._graph.invoke({"ctx": context, "reports": []})
        return ReviewResult(findings=out["ctx"].findings, reports=out.get("reports", []))


def build_review(config_get: ConfigLookup, default_model: str = "claude-opus-4-8") -> ProjectRiskReview:
    """Assemble the review pipeline from Admin-API config (enabled + model)."""
    builders = _builders()

    def _enabled_model(agent_key: str) -> tuple[bool, str]:
        cfg = config_get(agent_key)
        if cfg is None:
            return True, default_model
        return bool(cfg[0]), cfg[1]

    processors: list[tuple[str, FindingProcessor]] = []
    for key in PROCESSOR_ORDER:
        enabled, model = _enabled_model(key)
        if enabled:
            processors.append((key, builders[key](model)))

    reporters: list[Reporter] = []
    for key in REPORTER_AGENTS:
        enabled, model = _enabled_model(key)
        if enabled:
            reporters.append(builders[key](model))

    return ProjectRiskReview(processors, reporters)
