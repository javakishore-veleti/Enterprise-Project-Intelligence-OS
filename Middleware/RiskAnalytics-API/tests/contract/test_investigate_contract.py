"""Contract tests for POST /api/v1/analysis/investigate (fake facade, no LLM/DB).

Exercises routing, request validation, serialization, and error mapping only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from risk_analytics_api.api.dependencies import provide_investigate_project_facade
from risk_analytics_api.api.main import create_app
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.dtos.responses import (
    EvidenceCitation,
    InvestigationResponse,
    InvestigationStep,
)

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _response() -> InvestigationResponse:
    return InvestigationResponse(
        project_key="APACHE", question="why slipping?",
        hypotheses=["reopen churn"],
        steps=[InvestigationStep(action="reopened_issues(limit=5)",
                                 observation='{"count": 3}', hypothesis="reopen churn")],
        root_cause="High reopen rate concentrated in Auth",
        causal_chain=["rework churn", "schedule slip"],
        confidence=0.72,
        evidence=[EvidenceCitation(kind="reopened_issues", detail="3 record(s) matched", count=3)],
        recommended_action="Assign a single owner to Auth reopens",
        run_id="inv-1", generated_at=_NOW,
    )


class _FakeFacade:
    def execute(self, request):
        if request.project_key == "GHOST":
            raise NotFoundError(f"project '{request.project_key}' not found")
        return _response()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[provide_investigate_project_facade] = lambda: _FakeFacade()
    return TestClient(app)


def test_investigate_returns_conclusion() -> None:
    resp = _client().post("/api/v1/analysis/investigate",
                          json={"project_key": "APACHE", "question": "why slipping?"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["root_cause"] == "High reopen rate concentrated in Auth"
    assert body["confidence"] == 0.72
    assert body["steps"][0]["action"] == "reopened_issues(limit=5)"
    assert body["evidence"][0]["count"] == 3
    assert body["run_id"] == "inv-1"


def test_investigate_missing_project_maps_404() -> None:
    resp = _client().post("/api/v1/analysis/investigate", json={"project_key": "GHOST"})
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_investigate_requires_project_key() -> None:
    resp = _client().post("/api/v1/analysis/investigate", json={"question": "no key"})
    assert resp.status_code == 422
