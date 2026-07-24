"""Contract test for the dashboard activity endpoint with a fake facade.

No DB, no Mongo, no LLM — the facade is faked so this exercises routing,
serialization, and the JSON shape only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from risk_analytics_api.api.dependencies import provide_get_dashboard_activity_facade
from risk_analytics_api.api.main import create_app
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.responses import (
    AnalysisRunSummary,
    DashboardActivityResponse,
    DashboardFindingSummary,
    DashboardTotals,
)

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _activity() -> DashboardActivityResponse:
    return DashboardActivityResponse(
        recent_runs=[
            AnalysisRunSummary(
                run_id="run-2", project_key="SPARK", status=AnalysisStatus.COMPLETED,
                agent_keys=["schedule_risk"], started_at=_NOW, finished_at=_NOW,
                finding_count=3, report_count=1),
            AnalysisRunSummary(
                run_id="run-1", project_key="APACHE", status=AnalysisStatus.RUNNING,
                agent_keys=["quality_risk"], started_at=_NOW, finished_at=None,
                finding_count=0, report_count=0),
        ],
        recent_findings=[
            DashboardFindingSummary(
                finding_id="f2", run_id="run-2", project_key="SPARK",
                agent_key="schedule_risk", risk_category="schedule", severity="high",
                score=42.0, explanation="latest finding"),
            DashboardFindingSummary(
                finding_id="f1", run_id="run-1", project_key="APACHE",
                agent_key="quality_risk", risk_category="quality", severity="medium",
                score=21.0, explanation="older finding"),
        ],
        totals=DashboardTotals(total_runs=2, total_findings=6, projects_analyzed=2),
    )


class _FakeFacade:
    def __init__(self):
        self.limit = None
        self.projects = None

    def execute(self, limit, projects=None):
        self.limit = limit
        self.projects = projects
        return _activity()


def _client(facade) -> TestClient:
    app = create_app()
    app.dependency_overrides[provide_get_dashboard_activity_facade] = lambda: facade
    return TestClient(app)


def test_activity_shape_and_ordering() -> None:
    resp = _client(_FakeFacade()).get("/api/v1/analysis/activity")
    assert resp.status_code == 200
    body = resp.json()

    # recent_runs: newest first, with per-run counts.
    assert [r["run_id"] for r in body["recent_runs"]] == ["run-2", "run-1"]
    run = body["recent_runs"][0]
    assert set(run) == {
        "run_id", "project_key", "status", "agent_keys", "started_at",
        "finished_at", "finding_count", "report_count"}
    assert run["finding_count"] == 3 and run["report_count"] == 1

    # recent_findings: newest first, compact shape.
    assert [f["finding_id"] for f in body["recent_findings"]] == ["f2", "f1"]
    finding = body["recent_findings"][0]
    assert set(finding) == {
        "finding_id", "run_id", "project_key", "agent_key", "risk_category",
        "severity", "score", "explanation"}

    # totals.
    assert body["totals"] == {"total_runs": 2, "total_findings": 6, "projects_analyzed": 2}


def test_activity_default_limit_is_15() -> None:
    facade = _FakeFacade()
    _client(facade).get("/api/v1/analysis/activity")
    assert facade.limit == 15


def test_activity_respects_limit_query_param() -> None:
    facade = _FakeFacade()
    _client(facade).get("/api/v1/analysis/activity?limit=5")
    assert facade.limit == 5


def test_activity_rejects_out_of_range_limit() -> None:
    resp = _client(_FakeFacade()).get("/api/v1/analysis/activity?limit=0")
    assert resp.status_code == 422
