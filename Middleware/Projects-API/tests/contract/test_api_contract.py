"""Contract tests for the HTTP surface with fake DAOs (no MongoDB needed)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from projects_api.api.dependencies import (
    provide_get_project_facade,
    provide_get_project_metrics_facade,
    provide_search_projects_facade,
)
from projects_api.api.main import create_app
from projects_api.common.configuration import Settings
from projects_api.dtos.responses import ProjectMetricsResponse, ProjectResponse
from projects_api.facades.get_project import GetProjectFacade
from projects_api.facades.get_project_metrics import GetProjectMetricsFacade
from projects_api.facades.search_projects import SearchProjectsFacade
from projects_api.interfaces.daos import ProjectMetricsDao, ProjectsDao
from projects_api.services.project_metrics import DefaultProjectMetricsService
from projects_api.services.project_query import DefaultProjectQueryService

SAMPLE = [
    ProjectResponse(project_key="APACHE", name="Apache Server", issue_count=10, open_issue_count=3),
    ProjectResponse(project_key="SPARK", name="Spark Engine", issue_count=5, open_issue_count=1),
]


class _FakeProjectsDao(ProjectsDao):
    def search(self, query, limit, offset, project_keys=None):
        items = [p for p in SAMPLE if not query or query.lower() in p.project_key.lower()]
        if project_keys is not None:
            allowed = set(project_keys)
            items = [p for p in items if p.project_key in allowed]
        return items[offset : offset + limit], len(items)

    def search_scored(self, query, project_keys):
        return []

    def get(self, project_key):
        return next((p for p in SAMPLE if p.project_key == project_key), None)


class _FakeMetricsDao(ProjectMetricsDao):
    def latest(self, project_key):
        if project_key != "APACHE":
            return None
        return ProjectMetricsResponse(
            project_key="APACHE",
            computed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            backlog_growth=0.12,
            reopen_rate=0.05,
            blocker_count=2,
            dependency_depth=3,
        )

    def history(self, project_key, limit):
        m = self.latest(project_key)
        return [m] if m else []


def _client() -> TestClient:
    app = create_app()
    query_service = DefaultProjectQueryService(_FakeProjectsDao(), Settings())
    metrics_service = DefaultProjectMetricsService(_FakeMetricsDao())
    app.dependency_overrides[provide_search_projects_facade] = lambda: SearchProjectsFacade(query_service)
    app.dependency_overrides[provide_get_project_facade] = lambda: GetProjectFacade(query_service)
    app.dependency_overrides[provide_get_project_metrics_facade] = (
        lambda: GetProjectMetricsFacade(metrics_service)
    )
    return TestClient(app)


def test_liveness_ok() -> None:
    assert _client().get("/health/live").json()["status"] == "ok"


def test_search_projects() -> None:
    resp = _client().get("/api/v1/projects", params={"limit": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"]["total"] == 2
    assert {p["project_key"] for p in body["items"]} == {"APACHE", "SPARK"}


def test_get_project() -> None:
    resp = _client().get("/api/v1/projects/SPARK")
    assert resp.status_code == 200 and resp.json()["name"] == "Spark Engine"


def test_get_project_not_found() -> None:
    resp = _client().get("/api/v1/projects/NOPE")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_get_metrics() -> None:
    resp = _client().get("/api/v1/projects/APACHE/metrics")
    assert resp.status_code == 200 and resp.json()["blocker_count"] == 2


def test_get_metrics_missing_returns_404() -> None:
    resp = _client().get("/api/v1/projects/SPARK/metrics")
    assert resp.status_code == 404
