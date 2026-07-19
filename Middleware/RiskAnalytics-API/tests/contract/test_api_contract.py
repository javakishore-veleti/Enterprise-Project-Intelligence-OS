"""Contract tests for the HTTP surface with a fake orchestration facade.

No DB, no Mongo, no LLM — the orchestration is faked so this exercises routing,
serialization, and error mapping only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from risk_analytics_api.api.dependencies import (
    provide_get_analysis_run_facade,
    provide_start_project_analysis_facade,
)
from risk_analytics_api.api.main import create_app
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.responses import AnalysisRunResponse, RiskFindingResponse

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _run(run_id="run-1"):
    return AnalysisRunResponse(
        run_id=run_id, project_key="APACHE", status=AnalysisStatus.COMPLETED,
        agent_keys=["schedule_risk"], started_at=_NOW, finished_at=_NOW,
        findings=[RiskFindingResponse(
            finding_id="f1", agent_key="schedule_risk", risk_category="schedule",
            probability=0.6, impact=0.7, severity="high", score=42.0, confidence=0.8,
            explanation="test", assumptions=[], recommended_actions=["x"], affected=["APACHE"],
            analysis_timestamp=_NOW,
        )],
    )


class _FakeStart:
    def execute(self, project_key, request):
        return _run()


class _FakeGet:
    def execute(self, run_id):
        if run_id != "run-1":
            raise NotFoundError(f"run '{run_id}' not found")
        return _run(run_id)


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[provide_start_project_analysis_facade] = lambda: _FakeStart()
    app.dependency_overrides[provide_get_analysis_run_facade] = lambda: _FakeGet()
    return TestClient(app)


def test_liveness_ok() -> None:
    assert _client().get("/health/live").json()["status"] == "ok"


def test_start_analysis_returns_findings() -> None:
    resp = _client().post("/api/v1/analysis/projects/APACHE", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["findings"][0]["severity"] == "high"


def test_get_run() -> None:
    resp = _client().get("/api/v1/analysis/runs/run-1")
    assert resp.status_code == 200 and resp.json()["run_id"] == "run-1"


def test_get_run_not_found() -> None:
    resp = _client().get("/api/v1/analysis/runs/nope")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"
