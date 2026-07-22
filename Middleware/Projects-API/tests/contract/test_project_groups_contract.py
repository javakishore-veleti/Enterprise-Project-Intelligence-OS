"""Contract tests for the project-groups HTTP surface with a fake DAO."""
from __future__ import annotations

from fastapi.testclient import TestClient

from projects_api.api.dependencies import provide_project_groups_facade
from projects_api.api.main import create_app
from projects_api.dtos.responses import ProjectGroupResponse
from projects_api.facades.project_groups import ProjectGroupsFacade
from projects_api.interfaces.daos import ProjectGroupsDao
from projects_api.services.project_groups import DefaultProjectGroupsService


class _FakeGroupsDao(ProjectGroupsDao):
    def __init__(self) -> None:
        self._store: dict[str, ProjectGroupResponse] = {}

    def list_all(self):
        return sorted(self._store.values(), key=lambda g: g.created_at, reverse=True)

    def get(self, group_key):
        return self._store.get(group_key)

    def insert(self, record):
        self._store[record.group_key] = record
        return record

    def replace(self, record):
        self._store[record.group_key] = record
        return record

    def delete(self, group_key):
        return self._store.pop(group_key, None) is not None


def _client() -> TestClient:
    app = create_app()
    dao = _FakeGroupsDao()  # shared across requests for the app instance
    app.dependency_overrides[provide_project_groups_facade] = (
        lambda: ProjectGroupsFacade(DefaultProjectGroupsService(dao))
    )
    return TestClient(app)


def test_create_returns_201_with_slug_and_shape() -> None:
    c = _client()
    resp = c.post(
        "/api/v1/project-groups",
        json={"name": "My Team", "description": "desc", "project_keys": ["APACHE"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["group_key"] == "my-team"
    assert body["name"] == "My Team"
    assert body["description"] == "desc"
    assert body["project_keys"] == ["APACHE"]
    assert "created_at" in body and "updated_at" in body


def test_create_duplicate_returns_409() -> None:
    c = _client()
    c.post("/api/v1/project-groups", json={"name": "Team", "project_keys": []})
    resp = c.post("/api/v1/project-groups", json={"name": "team", "project_keys": []})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_list_returns_items() -> None:
    c = _client()
    c.post("/api/v1/project-groups", json={"name": "Alpha", "project_keys": []})
    c.post("/api/v1/project-groups", json={"name": "Beta", "project_keys": []})
    resp = c.get("/api/v1/project-groups")
    assert resp.status_code == 200
    keys = {g["group_key"] for g in resp.json()["items"]}
    assert keys == {"alpha", "beta"}


def test_get_returns_group_and_404_when_missing() -> None:
    c = _client()
    c.post("/api/v1/project-groups", json={"name": "Team", "project_keys": ["X"]})
    assert c.get("/api/v1/project-groups/team").json()["project_keys"] == ["X"]
    missing = c.get("/api/v1/project-groups/nope")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def test_update_partial_and_404_when_missing() -> None:
    c = _client()
    c.post(
        "/api/v1/project-groups",
        json={"name": "Team", "description": "old", "project_keys": ["A"]},
    )
    resp = c.put("/api/v1/project-groups/team", json={"description": "new"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "new"
    assert body["name"] == "Team"           # unchanged
    assert body["project_keys"] == ["A"]    # unchanged

    missing = c.put("/api/v1/project-groups/nope", json={"name": "x"})
    assert missing.status_code == 404


def test_delete_returns_204_and_404_when_missing() -> None:
    c = _client()
    c.post("/api/v1/project-groups", json={"name": "Team", "project_keys": []})
    assert c.delete("/api/v1/project-groups/team").status_code == 204
    assert c.delete("/api/v1/project-groups/team").status_code == 404
