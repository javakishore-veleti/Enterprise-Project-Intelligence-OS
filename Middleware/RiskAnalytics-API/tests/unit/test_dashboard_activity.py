"""Unit tests for the dashboard activity service with a fake DAO (no DB)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.responses import (
    AnalysisRunSummary,
    DashboardFindingSummary,
    DashboardTotals,
)
from risk_analytics_api.interfaces.daos import DashboardDao
from risk_analytics_api.services.dashboard import DefaultDashboardService

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _run(run_id: str, project_key: str, started: datetime) -> AnalysisRunSummary:
    return AnalysisRunSummary(
        run_id=run_id, project_key=project_key, status=AnalysisStatus.COMPLETED,
        agent_keys=["schedule_risk"], started_at=started, finished_at=started,
        finding_count=3, report_count=1)


def _finding(fid: str, project_key: str) -> DashboardFindingSummary:
    return DashboardFindingSummary(
        finding_id=fid, run_id="run-1", project_key=project_key, agent_key="schedule_risk",
        risk_category="schedule", severity="high", score=42.0, explanation="x")


class FakeDashboardDao(DashboardDao):
    def __init__(self):
        # Newest first (as the SQL ORDER BY DESC would return).
        self._runs = [
            _run("run-2", "SPARK", _NOW),
            _run("run-1", "APACHE", _NOW - timedelta(days=1)),
        ]
        self._findings = [_finding("f2", "SPARK"), _finding("f1", "APACHE")]
        self.limits: list[int] = []

    def recent_runs(self, limit):
        self.limits.append(limit)
        return self._runs[:limit]

    def recent_findings(self, limit):
        return self._findings[:limit]

    def totals(self):
        return DashboardTotals(total_runs=2, total_findings=6, projects_analyzed=2)


def test_activity_assembles_runs_findings_totals() -> None:
    service = DefaultDashboardService(FakeDashboardDao())
    result = service.activity(15)

    assert [r.run_id for r in result.recent_runs] == ["run-2", "run-1"]  # newest first
    assert [f.finding_id for f in result.recent_findings] == ["f2", "f1"]
    assert result.totals.total_runs == 2
    assert result.totals.total_findings == 6
    assert result.totals.projects_analyzed == 2


def test_activity_passes_limit_to_dao() -> None:
    dao = FakeDashboardDao()
    service = DefaultDashboardService(dao)
    result = service.activity(1)

    assert dao.limits == [1]
    assert len(result.recent_runs) == 1
    assert len(result.recent_findings) == 1
