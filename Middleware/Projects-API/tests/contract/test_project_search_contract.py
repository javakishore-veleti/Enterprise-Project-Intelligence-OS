"""Contract tests for GET /api/v1/projects/search (scale-hardened search).

Real facade + service wired to a fake DAO + fake assignments (no Mongo) — exercises
routing, the scope/q/limit/offset query params, the flat pager response shape,
and the per-user scoping seam.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from projects_api.api.dependencies import provide_search_projects_scoped_facade
from projects_api.api.main import create_app
from projects_api.common.configuration import Settings
from projects_api.dtos.common import ProjectSearchScoredRow
from projects_api.dtos.responses import ProjectResponse
from projects_api.facades.search_projects_scoped import SearchProjectsScopedFacade
from projects_api.interfaces.daos import ProjectAssignmentsDao
from projects_api.services.project_query import DefaultProjectQueryService
from tests.unit.test_project_query_service import FakeProjectsDao

SCORED = [
    ProjectSearchScoredRow(project_key="RISKY", name="Risky Service", open_issue_count=1000,
                           issue_count=1000, has_metrics=True, blocker_count=608,
                           reopen_rate=0.6, issue_aging_days=2067, critical_defect_ratio=0.9),
    ProjectSearchScoredRow(project_key="CALM", name="Calm Service", open_issue_count=2,
                           issue_count=100, has_metrics=True, blocker_count=0,
                           reopen_rate=0.0, issue_aging_days=5.0, critical_defect_ratio=0.0),
    ProjectSearchScoredRow(project_key="NEW", name="New Service", open_issue_count=4,
                           issue_count=4, has_metrics=False),
]

ASSIGNMENTS = {"mgr-calm": ["CALM"]}


class _FakeAssignmentsDao(ProjectAssignmentsDao):
    def project_keys_for(self, user_key: str) -> list[str]:
        return list(ASSIGNMENTS.get(user_key, []))


def _client() -> TestClient:
    app = create_app()
    service = DefaultProjectQueryService(
        FakeProjectsDao([ProjectResponse(project_key=r.project_key, name=r.name)
                         for r in SCORED], SCORED),
        Settings(),
    )
    app.dependency_overrides[provide_search_projects_scoped_facade] = (
        lambda: SearchProjectsScopedFacade(service, _FakeAssignmentsDao())
    )
    return TestClient(app)


def test_search_response_shape_and_ranking() -> None:
    resp = _client().get("/api/v1/projects/search")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"total", "returned", "offset", "limit", "items"}
    assert body["total"] == 3 and body["returned"] == 3
    assert body["offset"] == 0 and body["limit"] == 25
    keys = [i["project_key"] for i in body["items"]]
    assert keys == ["RISKY", "CALM", "NEW"]  # risk desc, unscored last
    item = body["items"][0]
    assert set(item) == {"project_key", "name", "risk_score", "risk_band", "open_issue_count"}
    assert item["risk_band"] == "High"
    assert body["items"][-1]["risk_score"] is None
    assert body["items"][-1]["risk_band"] is None


def test_search_route_not_shadowed_by_project_key() -> None:
    # the literal "/search" must resolve here, not GET /{project_key}
    body = _client().get("/api/v1/projects/search").json()
    assert "items" in body and "total" in body


def test_search_scoped_to_user_via_scope_param() -> None:
    resp = _client().get("/api/v1/projects/search?scope=mgr-calm")
    assert resp.status_code == 200
    body = resp.json()
    assert [i["project_key"] for i in body["items"]] == ["CALM"]
    assert body["total"] == 1


def test_search_unknown_scope_falls_back_to_all() -> None:
    body = _client().get("/api/v1/projects/search?scope=nobody").json()
    assert [i["project_key"] for i in body["items"]] == ["RISKY", "CALM", "NEW"]
    assert body["total"] == 3


def test_search_q_case_insensitive_on_key_or_name() -> None:
    body = _client().get("/api/v1/projects/search?q=calm").json()
    assert [i["project_key"] for i in body["items"]] == ["CALM"] and body["total"] == 1


def test_search_pagination() -> None:
    body = _client().get("/api/v1/projects/search?limit=1&offset=1").json()
    assert body["total"] == 3 and body["returned"] == 1
    assert body["items"][0]["project_key"] == "CALM"


def test_search_limit_over_100_rejected() -> None:
    assert _client().get("/api/v1/projects/search?limit=500").status_code == 422
