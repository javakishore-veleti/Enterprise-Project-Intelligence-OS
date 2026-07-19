"""Integration test for the real MongoDB DAO logic, backed by mongomock.

Exercises the actual find/regex/pagination/projection code without a live
MongoDB server. Skipped if mongomock is not installed.
"""
from __future__ import annotations

import pytest

mongomock = pytest.importorskip("mongomock")

from projects_api.daos.projects import MongoProjectsDao


class _FakeDatabase:
    """Adapts a mongomock database to the DAO's ``Database.db()`` surface."""

    def __init__(self, mongo_db) -> None:
        self._db = mongo_db

    def db(self):
        return self._db


@pytest.fixture()
def dao():
    client = mongomock.MongoClient()
    db = client["epi_os"]
    db["projects"].insert_many([
        {"project_key": "APACHE", "name": "Apache Server", "issue_count": 10, "open_issue_count": 3},
        {"project_key": "SPARK", "name": "Spark Engine", "issue_count": 5, "open_issue_count": 1},
        {"project_key": "KAFKA", "name": "Kafka Broker", "issue_count": 8, "open_issue_count": 2},
    ])
    return MongoProjectsDao(_FakeDatabase(db))


def test_search_all_sorted_with_total(dao) -> None:
    items, total = dao.search(None, limit=10, offset=0)
    assert total == 3
    assert [p.project_key for p in items] == ["APACHE", "KAFKA", "SPARK"]  # sorted by key


def test_search_regex_case_insensitive(dao) -> None:
    items, total = dao.search("spark", limit=10, offset=0)
    assert total == 1 and items[0].project_key == "SPARK"


def test_search_pagination(dao) -> None:
    items, total = dao.search(None, limit=1, offset=1)
    assert total == 3 and len(items) == 1 and items[0].project_key == "KAFKA"


def test_get_and_projection_excludes_id(dao) -> None:
    p = dao.get("APACHE")
    assert p is not None and p.issue_count == 10
    assert dao.get("MISSING") is None
