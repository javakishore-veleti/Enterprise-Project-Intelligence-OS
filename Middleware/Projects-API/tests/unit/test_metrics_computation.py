"""Tests for deterministic metrics computation — pure helpers + mongomock engine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from projects_api.services.metrics_computation import (
    backlog_growth,
    dependency_depth,
    reopen_rate,
)


# --- pure helpers ---------------------------------------------------------- #
def test_backlog_growth() -> None:
    assert backlog_growth(created_in_window=30, resolved_in_window=10, open_issue_count=100) == 0.2
    assert backlog_growth(5, 15, 50) == -0.2   # backlog shrinking
    assert backlog_growth(5, 5, 0) == 0.0      # no divide-by-zero


def test_reopen_rate() -> None:
    assert reopen_rate(3, 12) == 0.25
    assert reopen_rate(1, 0) == 1.0  # guarded denominator


def test_dependency_depth_linear_chain() -> None:
    assert dependency_depth([("A", "B"), ("B", "C"), ("C", "D")]) == 4


def test_dependency_depth_branches_take_longest() -> None:
    assert dependency_depth([("A", "B"), ("A", "C"), ("C", "D")]) == 3  # A->C->D


def test_dependency_depth_is_cycle_safe() -> None:
    assert dependency_depth([("A", "B"), ("B", "A")]) >= 1  # does not hang
    assert dependency_depth([]) == 0


# --- engine against mongomock --------------------------------------------- #
mongomock = pytest.importorskip("mongomock")

from projects_api.daos.metrics_computation import MongoMetricsComputationDao  # noqa: E402
from projects_api.daos.projects import MongoProjectsDao  # noqa: E402
from projects_api.services.metrics_computation import (  # noqa: E402
    DefaultMetricsComputationService,
)


class _FakeDatabase:
    def __init__(self, db):
        self._db = db

    def db(self):
        return self._db


@pytest.fixture()
def service_and_db():
    db = mongomock.MongoClient()["epi_os"]
    ref = datetime(2025, 6, 1, tzinfo=timezone.utc)
    in_window = ref - timedelta(days=10)
    old = ref - timedelta(days=200)

    db["projects"].insert_one({"project_key": "APACHE", "name": "Apache"})
    issues = []
    # 6 open (2 blockers), 4 resolved. 3 created in-window; 1 resolved in-window.
    for i in range(6):
        issues.append({"issue_key": f"AP-{i}", "project_key": "APACHE", "status": "Open",
                       "priority": "Blocker" if i < 2 else "Major",
                       "created_at": in_window if i < 3 else old, "resolved_at": None})
    for i in range(6, 10):
        issues.append({"issue_key": f"AP-{i}", "project_key": "APACHE", "status": "Resolved",
                       "priority": "Major", "created_at": old,
                       "resolved_at": in_window if i == 6 else old})
    db["issues"].insert_many(issues)
    # one reopened issue
    db["issue_histories"].insert_one({"issue_key": "AP-6", "project_key": "APACHE",
                                     "field": "status", "to_value": "Reopened"})
    # dependency chain AP-0 -> AP-1 -> AP-2  (depth 3)
    db["issue_links"].insert_many([
        {"project_key": "APACHE", "source_issue_key": "AP-0", "target_issue_key": "AP-1", "link_type": "blocks"},
        {"project_key": "APACHE", "source_issue_key": "AP-1", "target_issue_key": "AP-2", "link_type": "blocks"},
    ])

    fake = _FakeDatabase(db)
    service = DefaultMetricsComputationService(MongoMetricsComputationDao(fake), MongoProjectsDao(fake))
    return service, db


def test_compute_produces_grounded_metrics(service_and_db) -> None:
    service, db = service_and_db
    m = service.compute("APACHE")

    assert m.blocker_count == 2
    assert m.reopen_rate == 0.25            # 1 reopened / 4 resolved
    assert m.dependency_depth == 3          # AP-0 -> AP-1 -> AP-2
    # backlog_growth = (created_in_window 3 - resolved_in_window 1) / open(6)
    assert m.backlog_growth == round(2 / 6, 3)

    # persisted to project_metrics + project counts updated
    assert db["project_metrics"].count_documents({"project_key": "APACHE"}) == 1
    proj = db["projects"].find_one({"project_key": "APACHE"})
    assert proj["issue_count"] == 10 and proj["open_issue_count"] == 6


def test_compute_all_iterates_projects(service_and_db) -> None:
    service, _ = service_and_db
    assert service.compute_all(limit=10) == ["APACHE"]
