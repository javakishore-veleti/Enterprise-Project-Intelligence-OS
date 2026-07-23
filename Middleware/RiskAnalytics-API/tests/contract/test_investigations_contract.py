"""Contract tests for the investigation history + templates endpoints.

Fake facades (no service/DB/LLM) — exercises routing, query params,
serialization, and error mapping only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from risk_analytics_api.api.dependencies import (
    provide_get_investigation_facade,
    provide_list_investigation_templates_facade,
    provide_list_investigations_facade,
)
from risk_analytics_api.api.main import create_app
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.dtos.responses import (
    InvestigationResponse,
    InvestigationsPageResponse,
    InvestigationSummary,
    InvestigationTemplateResponse,
)

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


class _FakeListFacade:
    def __init__(self):
        self.calls = []

    def execute(self, scope, q, limit, offset, projects=None):
        self.calls.append((scope, q, limit, offset, projects))
        return InvestigationsPageResponse(
            total=1, returned=1, offset=offset, limit=limit,
            items=[InvestigationSummary(
                investigation_id="inv-1", project_key="APACHE", question="why slipping?",
                template_key="quality", status="COMPLETED", root_cause="High reopen rate",
                confidence=0.72, created_at=_NOW)],
        )


class _FakeGetFacade:
    def execute(self, investigation_id):
        if investigation_id == "missing":
            raise NotFoundError(f"investigation '{investigation_id}' not found")
        return InvestigationResponse(
            investigation_id=investigation_id, project_key="APACHE", question="why?",
            template_key="full", status="COMPLETED", root_cause="High reopen rate",
            causal_chain=["churn", "slip"], confidence=0.72, recommended_action="Assign owner",
            run_id="run-1", generated_at=_NOW)


class _FakeTemplatesFacade:
    def execute(self):
        return [
            InvestigationTemplateResponse(template_key="full", name="Full investigation",
                                          description="all angles", steps=["a", "b"], editable=True),
            InvestigationTemplateResponse(template_key="quality", name="Quality & reopen churn",
                                          description="quality", steps=["reopen"], editable=True),
        ]


def _client(list_facade=None):
    app = create_app()
    app.dependency_overrides[provide_list_investigations_facade] = lambda: list_facade or _FakeListFacade()
    app.dependency_overrides[provide_get_investigation_facade] = lambda: _FakeGetFacade()
    app.dependency_overrides[provide_list_investigation_templates_facade] = lambda: _FakeTemplatesFacade()
    return TestClient(app)


def test_list_investigations_page_shape() -> None:
    resp = _client().get("/api/v1/analysis/investigations?limit=20&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"total", "returned", "offset", "limit", "items"}
    assert body["total"] == 1 and body["returned"] == 1
    item = body["items"][0]
    assert set(item) == {"investigation_id", "project_key", "question", "template_key",
                         "status", "root_cause", "confidence", "created_at"}
    assert item["investigation_id"] == "inv-1"
    assert item["created_at"].startswith("2026-07-01")  # ISO-8601 string


def test_list_passes_scope_and_query() -> None:
    facade = _FakeListFacade()
    resp = _client(list_facade=facade).get(
        "/api/v1/analysis/investigations?scope=alice&q=reopen&limit=5&offset=2")
    assert resp.status_code == 200
    assert facade.calls == [("alice", "reopen", 5, 2, None)]


def test_list_passes_parsed_projects_filter() -> None:
    facade = _FakeListFacade()
    resp = _client(list_facade=facade).get(
        "/api/v1/analysis/investigations?projects=APACHE,%20BILLING")
    assert resp.status_code == 200
    # comma-separated -> parsed, trimmed list threaded to the facade
    assert facade.calls == [(None, None, 20, 0, ["APACHE", "BILLING"])]


def test_list_absent_projects_is_none() -> None:
    facade = _FakeListFacade()
    _client(list_facade=facade).get("/api/v1/analysis/investigations")
    assert facade.calls == [(None, None, 20, 0, None)]


def test_get_investigation_returns_full_conclusion() -> None:
    resp = _client().get("/api/v1/analysis/investigations/inv-9")
    assert resp.status_code == 200
    body = resp.json()
    assert body["investigation_id"] == "inv-9"
    assert body["status"] == "COMPLETED"
    assert body["template_key"] == "full"
    assert body["root_cause"] == "High reopen rate"


def test_get_missing_investigation_maps_404() -> None:
    resp = _client().get("/api/v1/analysis/investigations/missing")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_list_templates_shape() -> None:
    resp = _client().get("/api/v1/analysis/investigation-templates")
    assert resp.status_code == 200
    body = resp.json()
    assert [t["template_key"] for t in body] == ["full", "quality"]
    assert set(body[0]) == {"template_key", "name", "description", "steps", "editable"}


def test_list_limit_over_100_rejected() -> None:
    resp = _client().get("/api/v1/analysis/investigations?limit=500")
    assert resp.status_code == 422
