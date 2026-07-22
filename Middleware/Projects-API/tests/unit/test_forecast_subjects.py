"""Tests for the forecast-subjects facets endpoint (release/component/tag).

Exercises the Mongo aggregation (unwind -> count -> sort -> cap) against
mongomock, plus the service's project-existence guard. Hermetic — no real infra.
"""
from __future__ import annotations

import pytest

from projects_api.common.exceptions import NotFoundError

mongomock = pytest.importorskip("mongomock")

from projects_api.daos.forecast_subjects import MongoForecastSubjectsDao  # noqa: E402
from projects_api.daos.projects import MongoProjectsDao  # noqa: E402
from projects_api.services.forecast_subjects import DefaultForecastSubjectsService  # noqa: E402


class _FakeDatabase:
    def __init__(self, db):
        self._db = db

    def db(self):
        return self._db


@pytest.fixture()
def service_and_db():
    db = mongomock.MongoClient()["epi_os"]
    db["projects"].insert_one({"project_key": "APACHE", "name": "Apache"})
    # 3 issues on 2.0, 1 on 1.0; components/labels vary; one issue has no arrays.
    db["issues"].insert_many([
        {"issue_key": "AP-1", "project_key": "APACHE", "fix_versions": ["2.0"],
         "components": ["core", "api"], "labels": ["perf"]},
        {"issue_key": "AP-2", "project_key": "APACHE", "fix_versions": ["2.0"],
         "components": ["core"], "labels": ["perf", "ux"]},
        {"issue_key": "AP-3", "project_key": "APACHE", "fix_versions": ["2.0", "1.0"],
         "components": ["api"], "labels": []},
        {"issue_key": "AP-4", "project_key": "APACHE", "fix_versions": ["1.0"],
         "components": [], "labels": ["perf"]},
        # a foreign-project issue that must never leak in
        {"issue_key": "SP-1", "project_key": "SPARK", "fix_versions": ["2.0"],
         "components": ["core"], "labels": ["perf"]},
    ])
    service = DefaultForecastSubjectsService(
        MongoForecastSubjectsDao(_FakeDatabase(db)), MongoProjectsDao(_FakeDatabase(db)))
    return service, db


def test_facets_counts_sorted_desc_and_scoped(service_and_db) -> None:
    service, _ = service_and_db
    resp = service.subjects("APACHE")

    assert resp.project_key == "APACHE"
    releases = {f.value: f.count for f in resp.releases}
    assert releases == {"2.0": 3, "1.0": 2}
    # sorted by count desc -> 2.0 first
    assert resp.releases[0].value == "2.0"

    components = {f.value: f.count for f in resp.components}
    assert components == {"core": 2, "api": 2}

    tags = {f.value: f.count for f in resp.tags}
    assert tags == {"perf": 3, "ux": 1}


def test_facets_empty_when_no_subject_fields(service_and_db) -> None:
    service, db = service_and_db
    db["projects"].insert_one({"project_key": "BLANK", "name": "Blank"})
    db["issues"].insert_one({"issue_key": "B-1", "project_key": "BLANK"})
    resp = service.subjects("BLANK")
    assert resp.releases == [] and resp.components == [] and resp.tags == []


def test_missing_project_raises_not_found(service_and_db) -> None:
    service, _ = service_and_db
    with pytest.raises(NotFoundError):
        service.subjects("GHOST")


def test_cap_limits_returned_values() -> None:
    db = mongomock.MongoClient()["epi_os"]
    db["projects"].insert_one({"project_key": "BIG", "name": "Big"})
    db["issues"].insert_many([
        {"issue_key": f"B-{i}", "project_key": "BIG", "fix_versions": [f"v{i}"]}
        for i in range(60)
    ])
    dao = MongoForecastSubjectsDao(_FakeDatabase(db))
    resp = dao.facets("BIG", cap=50)
    assert len(resp.releases) == 50
