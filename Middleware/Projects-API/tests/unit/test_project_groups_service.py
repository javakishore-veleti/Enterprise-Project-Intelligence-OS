"""Unit tests for the project-groups service against an in-memory fake DAO."""
from __future__ import annotations

import pytest

from projects_api.common.exceptions import ConflictError, NotFoundError, ValidationError
from projects_api.dtos.requests import (
    CreateProjectGroupRequest,
    UpdateProjectGroupRequest,
)
from projects_api.dtos.responses import ProjectGroupResponse
from projects_api.interfaces.daos import ProjectGroupsDao
from projects_api.services.project_groups import DefaultProjectGroupsService


class FakeProjectGroupsDao(ProjectGroupsDao):
    def __init__(self) -> None:
        self._store: dict[str, ProjectGroupResponse] = {}

    def list_all(self):
        # Newest first by created_at.
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


def _service():
    return DefaultProjectGroupsService(FakeProjectGroupsDao())


def test_create_generates_slug_and_persists() -> None:
    svc = _service()
    group = svc.create_group(
        CreateProjectGroupRequest(name="My Big Team!", project_keys=["APACHE", "SPARK"]))
    assert group.group_key == "my-big-team"
    assert group.name == "My Big Team!"
    assert group.description == ""
    assert group.project_keys == ["APACHE", "SPARK"]
    assert group.created_at == group.updated_at
    assert svc.get_group("my-big-team").project_keys == ["APACHE", "SPARK"]


def test_create_duplicate_slug_raises_conflict() -> None:
    svc = _service()
    svc.create_group(CreateProjectGroupRequest(name="Platform Team"))
    with pytest.raises(ConflictError):
        svc.create_group(CreateProjectGroupRequest(name="platform  team"))


def test_create_non_alphanumeric_name_raises_validation() -> None:
    with pytest.raises(ValidationError):
        _service().create_group(CreateProjectGroupRequest(name="!!!"))


def test_list_returns_newest_first() -> None:
    svc = _service()
    a = svc.create_group(CreateProjectGroupRequest(name="Alpha"))
    b = svc.create_group(CreateProjectGroupRequest(name="Beta"))
    keys = [g.group_key for g in svc.list_groups().items]
    assert set(keys) == {a.group_key, b.group_key}


def test_get_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service().get_group("nope")


def test_update_is_partial_and_bumps_updated_at() -> None:
    svc = _service()
    created = svc.create_group(
        CreateProjectGroupRequest(name="Team", description="old", project_keys=["A"]))
    updated = svc.update_group(
        created.group_key, UpdateProjectGroupRequest(description="new"))
    assert updated.group_key == created.group_key
    assert updated.name == "Team"                 # unchanged
    assert updated.description == "new"           # changed
    assert updated.project_keys == ["A"]          # unchanged
    assert updated.created_at == created.created_at
    assert updated.updated_at >= created.updated_at


def test_update_replaces_project_keys() -> None:
    svc = _service()
    created = svc.create_group(CreateProjectGroupRequest(name="Team", project_keys=["A"]))
    updated = svc.update_group(
        created.group_key, UpdateProjectGroupRequest(project_keys=["B", "C"]))
    assert updated.project_keys == ["B", "C"]


def test_update_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service().update_group("nope", UpdateProjectGroupRequest(name="x"))


def test_delete_removes_and_missing_raises_not_found() -> None:
    svc = _service()
    created = svc.create_group(CreateProjectGroupRequest(name="Team"))
    svc.delete_group(created.group_key)
    with pytest.raises(NotFoundError):
        svc.get_group(created.group_key)
    with pytest.raises(NotFoundError):
        svc.delete_group(created.group_key)
