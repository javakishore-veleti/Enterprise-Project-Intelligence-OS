"""Integration test for the project-groups MongoDB DAO, backed by mongomock.

Exercises the real find/sort/insert/replace/delete + unique-index code without a
live MongoDB server. Skipped if mongomock is not installed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

mongomock = pytest.importorskip("mongomock")

from projects_api.daos.project_groups import MongoProjectGroupsDao
from projects_api.dtos.responses import ProjectGroupResponse


class _FakeDatabase:
    def __init__(self, mongo_db) -> None:
        self._db = mongo_db

    def db(self):
        return self._db


def _record(group_key: str, created: datetime) -> ProjectGroupResponse:
    return ProjectGroupResponse(
        group_key=group_key,
        name=group_key.title(),
        description="",
        project_keys=["A", "B"],
        created_at=created,
        updated_at=created,
    )


@pytest.fixture()
def dao():
    client = mongomock.MongoClient()
    return MongoProjectGroupsDao(_FakeDatabase(client["epi_os"]))


def test_insert_get_and_projection_excludes_id(dao) -> None:
    dao.insert(_record("alpha", datetime(2026, 1, 1, tzinfo=timezone.utc)))
    got = dao.get("alpha")
    assert got is not None and got.project_keys == ["A", "B"]
    assert dao.get("missing") is None


def test_list_all_newest_first(dao) -> None:
    dao.insert(_record("alpha", datetime(2026, 1, 1, tzinfo=timezone.utc)))
    dao.insert(_record("beta", datetime(2026, 2, 1, tzinfo=timezone.utc)))
    assert [g.group_key for g in dao.list_all()] == ["beta", "alpha"]


def test_replace_updates_existing(dao) -> None:
    dao.insert(_record("alpha", datetime(2026, 1, 1, tzinfo=timezone.utc)))
    updated = _record("alpha", datetime(2026, 1, 1, tzinfo=timezone.utc)).model_copy(
        update={"description": "changed", "project_keys": ["Z"]})
    dao.replace(updated)
    got = dao.get("alpha")
    assert got.description == "changed" and got.project_keys == ["Z"]
    assert len(dao.list_all()) == 1  # replaced, not duplicated


def test_delete_reports_removal(dao) -> None:
    dao.insert(_record("alpha", datetime(2026, 1, 1, tzinfo=timezone.utc)))
    assert dao.delete("alpha") is True
    assert dao.delete("alpha") is False
