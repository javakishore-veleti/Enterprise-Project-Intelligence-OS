"""Graph-path tests for the risk-review LangGraph pipeline (fakes, no LLM)."""
from __future__ import annotations

from datetime import datetime, timezone

from agent_core import (
    EvidenceMetrics,
    EvidencePackage,
    FindingProcessor,
    ReportKind,
    Reporter,
    ReviewContext,
    RiskCategory,
    RiskFinding,
    RiskReport,
    Severity,
)

from risk_analytics_api.graphs.risk_review import ProjectRiskReview

_EVID = EvidencePackage(project_key="APACHE", project_name="Apache", metrics=EvidenceMetrics())


def _finding(score: float) -> RiskFinding:
    return RiskFinding(
        risk_category=RiskCategory.SCHEDULE, probability=0.6, impact=0.6, severity=Severity.MEDIUM,
        score=score, confidence=0.8, explanation="f", source_agent="schedule_risk",
        analysis_timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _ctx(findings):
    return ReviewContext(project_key="APACHE", project_name="Apache", evidence=_EVID, findings=findings)


class _TagProcessor(FindingProcessor):
    """Records order and stamps its name into each finding's meta."""

    def __init__(self, name, order_log):
        self.agent_key = name
        self._log = order_log

    def process(self, context):
        self._log.append(self.agent_key)
        return [f.model_copy(update={"meta": {**f.meta, self.agent_key: True}}) for f in context.findings]


class _DropAllProcessor(FindingProcessor):
    agent_key = "dropper"

    def process(self, context):
        return []


class _FakeReporter(Reporter):
    def __init__(self, kind, order_log):
        self.agent_key = f"reporter_{kind.value}"
        self._kind = kind
        self._log = order_log

    def report(self, context):
        self._log.append(self.agent_key)
        return RiskReport(
            kind=self._kind, title=f"{self._kind.value} report",
            summary=f"{len(context.findings)} findings", sections=[],
            source_agent=self.agent_key, generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )


def test_pipeline_runs_processors_in_order_then_reporters() -> None:
    log: list[str] = []
    review = ProjectRiskReview(
        processors=[("a", _TagProcessor("a", log)), ("b", _TagProcessor("b", log))],
        reporters=[_FakeReporter(ReportKind.PROJECT, log), _FakeReporter(ReportKind.EXECUTIVE, log)],
    )

    result = review.run(_ctx([_finding(50), _finding(30)]))

    assert log == ["a", "b", "reporter_project", "reporter_executive"]  # order preserved
    assert all(f.meta.get("a") and f.meta.get("b") for f in result.findings)  # both applied
    assert {r.kind.value for r in result.reports} == {"project", "executive"}
    assert result.reports[0].summary == "2 findings"  # reporters saw post-processing findings


def test_processor_that_drops_all_yields_empty_findings_and_reporters_still_run() -> None:
    log: list[str] = []
    review = ProjectRiskReview(
        processors=[("dropper", _DropAllProcessor())],
        reporters=[_FakeReporter(ReportKind.MITIGATION, log)],
    )
    result = review.run(_ctx([_finding(50)]))
    assert result.findings == []
    assert len(result.reports) == 1 and result.reports[0].summary == "0 findings"


def test_pipeline_with_no_processors_or_reporters() -> None:
    review = ProjectRiskReview(processors=[], reporters=[])
    result = review.run(_ctx([_finding(50)]))
    assert len(result.findings) == 1 and result.reports == []
