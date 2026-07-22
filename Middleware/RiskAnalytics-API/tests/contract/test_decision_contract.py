"""Contract tests for the Decide endpoints (fake facades, no service/LLM/DB).

Exercises routing, request validation, serialization (option + page shapes,
uuid->str, question:null), and error mapping (404/422) only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from risk_analytics_api.api.dependencies import (
    provide_approve_decision_facade,
    provide_get_decision_facade,
    provide_list_decisions_facade,
    provide_run_decision_facade,
    provide_select_option_facade,
)
from risk_analytics_api.api.main import create_app
from risk_analytics_api.common.exceptions import NotFoundError, ValidationError
from risk_analytics_api.dtos.responses import (
    DecisionOption,
    DecisionResponse,
    DecisionsPageResponse,
    DecisionSummary,
)

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _decision(status="DRAFTED", selected=None, approved=None) -> DecisionResponse:
    return DecisionResponse(
        decision_id="dc-1", project_key="APACHE", question=None,
        options=[
            DecisionOption(option_id="opt-1", title="Reprioritize blockers",
                           summary="clear the constraint", actions=["Triage", "Pair"],
                           suggested_owners=["alice", "bob"],
                           predicted_outcome="stabilizes", tradeoffs="slows features",
                           recovery_estimate="2-4 weeks", confidence=0.7),
            DecisionOption(option_id="opt-2", title="Add capacity",
                           actions=["Onboard 1 dev"], suggested_owners=["alice"]),
        ],
        selected_option_id=selected, status=status, narrative="prefer opt-1",
        confidence=0.72, run_id="run-1", created_at=_NOW, approved_at=approved,
    )


class _FakeRunDecision:
    def execute(self, request):
        if request.project_key == "GHOST":
            raise NotFoundError("project 'GHOST' not found")
        return _decision()


class _FakeSelect:
    def execute(self, decision_id, request):
        if decision_id == "missing":
            raise NotFoundError(f"decision '{decision_id}' not found")
        if request.option_id not in {"opt-1", "opt-2"}:
            raise ValidationError(f"option '{request.option_id}' is not one of this decision's options")
        return _decision(status="SELECTED", selected=request.option_id)


class _FakeApprove:
    def execute(self, decision_id):
        if decision_id == "missing":
            raise NotFoundError(f"decision '{decision_id}' not found")
        return _decision(status="APPROVED", selected="opt-1", approved=_NOW)


class _FakeGet:
    def execute(self, decision_id):
        if decision_id == "missing":
            raise NotFoundError(f"decision '{decision_id}' not found")
        return _decision()


class _FakeList:
    def __init__(self):
        self.calls = []

    def execute(self, scope, q, limit, offset):
        self.calls.append((scope, q, limit, offset))
        return DecisionsPageResponse(
            total=1, returned=1, offset=offset, limit=limit,
            items=[DecisionSummary(decision_id="dc-1", project_key="APACHE",
                                   status="DRAFTED", option_count=2,
                                   selected_option_id=None, confidence=0.72,
                                   created_at=_NOW)])


def _client(list_facade=None):
    app = create_app()
    o = app.dependency_overrides
    o[provide_run_decision_facade] = lambda: _FakeRunDecision()
    o[provide_select_option_facade] = lambda: _FakeSelect()
    o[provide_approve_decision_facade] = lambda: _FakeApprove()
    o[provide_get_decision_facade] = lambda: _FakeGet()
    o[provide_list_decisions_facade] = lambda: list_facade or _FakeList()
    return TestClient(app)


def test_run_decision_returns_options_201() -> None:
    resp = _client().post("/api/v1/analysis/decide", json={"project_key": "APACHE"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["decision_id"] == "dc-1" and body["question"] is None
    assert body["status"] == "DRAFTED" and body["selected_option_id"] is None
    assert [o["option_id"] for o in body["options"]] == ["opt-1", "opt-2"]
    assert body["options"][0]["suggested_owners"] == ["alice", "bob"]
    assert body["options"][0]["actions"] == ["Triage", "Pair"]


def test_run_decision_requires_project_key() -> None:
    assert _client().post("/api/v1/analysis/decide", json={}).status_code == 422


def test_run_decision_missing_project_maps_404() -> None:
    resp = _client().post("/api/v1/analysis/decide", json={"project_key": "GHOST"})
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_select_option_sets_state() -> None:
    resp = _client().post("/api/v1/analysis/decisions/dc-1/select", json={"option_id": "opt-2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SELECTED" and body["selected_option_id"] == "opt-2"


def test_select_requires_option_id() -> None:
    assert _client().post(
        "/api/v1/analysis/decisions/dc-1/select", json={}).status_code == 422


def test_select_unknown_option_maps_422() -> None:
    resp = _client().post("/api/v1/analysis/decisions/dc-1/select", json={"option_id": "opt-9"})
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "validation_error"


def test_select_missing_decision_maps_404() -> None:
    resp = _client().post("/api/v1/analysis/decisions/missing/select", json={"option_id": "opt-1"})
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_approve_sets_approved_state() -> None:
    resp = _client().post("/api/v1/analysis/decisions/dc-1/approve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "APPROVED" and body["approved_at"] is not None


def test_approve_missing_decision_maps_404() -> None:
    resp = _client().post("/api/v1/analysis/decisions/missing/approve")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_list_decisions_page_shape() -> None:
    resp = _client().get("/api/v1/analysis/decisions?limit=20&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"total", "returned", "offset", "limit", "items"}
    item = body["items"][0]
    assert set(item) == {"decision_id", "project_key", "status", "option_count",
                         "selected_option_id", "confidence", "created_at"}


def test_list_decisions_passes_scope_and_query() -> None:
    facade = _FakeList()
    _client(list_facade=facade).get(
        "/api/v1/analysis/decisions?scope=alice&q=blocker&limit=5&offset=2")
    assert facade.calls == [("alice", "blocker", 5, 2)]


def test_list_decisions_limit_over_100_rejected() -> None:
    assert _client().get("/api/v1/analysis/decisions?limit=500").status_code == 422


def test_get_decision_full_and_404() -> None:
    assert _client().get("/api/v1/analysis/decisions/dc-1").status_code == 200
    missing = _client().get("/api/v1/analysis/decisions/missing")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
