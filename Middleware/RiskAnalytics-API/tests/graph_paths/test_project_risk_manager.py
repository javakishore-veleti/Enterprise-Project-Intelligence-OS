"""Graph-path tests for the LangGraph project-risk manager fan-out.

Exercises the real LangGraph graph with fake agents (no LLM): multiple agents
fan out and their findings merge; a failing agent records an error without
aborting the others; unimplemented agents (factory returns None) are skipped.
"""
from __future__ import annotations

from datetime import datetime, timezone

from agent_core import (
    EvidenceMetrics,
    EvidencePackage,
    RiskAgent,
    RiskCategory,
    RiskFinding,
    Severity,
)

from risk_analytics_api.graphs.project_risk_manager import ProjectRiskManager

EVIDENCE = EvidencePackage(
    project_key="APACHE", project_name="Apache", metrics=EvidenceMetrics(blocker_count=5)
)


def _finding(agent_key: str, category: RiskCategory) -> RiskFinding:
    return RiskFinding(
        risk_category=category, probability=0.5, impact=0.5, severity=Severity.MEDIUM,
        score=25.0, confidence=0.7, explanation=f"{agent_key} finding",
        source_agent=agent_key, analysis_timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


class _FakeAgent(RiskAgent):
    def __init__(self, agent_key, category):
        self.agent_key = agent_key
        self.category = category

    def analyze(self, evidence):
        return [_finding(self.agent_key, self.category)]


class _BoomAgent(RiskAgent):
    agent_key = "boom"
    category = RiskCategory.SCHEDULE

    def analyze(self, evidence):
        raise RuntimeError("model exploded")


def _factory(mapping):
    def build(agent_key, framework, model):
        return mapping.get(agent_key)
    return build


def test_fan_out_merges_findings_from_multiple_agents() -> None:
    factory = _factory({
        "schedule_risk": _FakeAgent("schedule_risk", RiskCategory.SCHEDULE),
        "quality_risk": _FakeAgent("quality_risk", RiskCategory.QUALITY),
    })
    manager = ProjectRiskManager(factory)

    result = manager.run(EVIDENCE, [
        ("schedule_risk", "langgraph", "m"),
        ("quality_risk", "langgraph", "m"),
    ])

    assert not result.errors
    agents = sorted(f.source_agent for f in result.findings)
    assert agents == ["quality_risk", "schedule_risk"]


def test_one_failing_agent_does_not_abort_others() -> None:
    factory = _factory({
        "schedule_risk": _FakeAgent("schedule_risk", RiskCategory.SCHEDULE),
        "boom": _BoomAgent(),
    })
    manager = ProjectRiskManager(factory)

    result = manager.run(EVIDENCE, [
        ("schedule_risk", "langgraph", "m"),
        ("boom", "langgraph", "m"),
    ])

    assert [f.source_agent for f in result.findings] == ["schedule_risk"]
    assert len(result.errors) == 1 and result.errors[0]["agent_key"] == "boom"


def test_unimplemented_agent_skipped() -> None:
    manager = ProjectRiskManager(_factory({}))  # factory returns None for everything
    result = manager.run(EVIDENCE, [("quality_risk", "langgraph", "m")])
    assert result.findings == [] and result.errors == []


def test_no_specs_returns_empty() -> None:
    manager = ProjectRiskManager(_factory({}))
    result = manager.run(EVIDENCE, [])
    assert result.findings == [] and result.errors == []
