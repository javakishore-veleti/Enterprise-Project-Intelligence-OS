"""Unit tests for the project query service against an in-memory fake DAO."""
from __future__ import annotations

import pytest

from projects_api.common.configuration import Settings
from projects_api.common.exceptions import NotFoundError
from projects_api.dtos.common import ProjectSearchScoredRow
from projects_api.dtos.requests import ScopedProjectSearchRequest, SearchProjectsRequest
from projects_api.dtos.responses import ProjectResponse
from projects_api.interfaces.daos import ProjectsDao
from projects_api.services.project_query import DefaultProjectQueryService


class FakeProjectsDao(ProjectsDao):
    def __init__(
        self,
        projects: list[ProjectResponse],
        scored_rows: list[ProjectSearchScoredRow] | None = None,
    ) -> None:
        self._projects = projects
        self._scored_rows = scored_rows or []

    def search(self, query, limit, offset, project_keys=None):
        matched = [
            p for p in self._projects
            if not query or query.lower() in p.project_key.lower() or query.lower() in p.name.lower()
        ]
        if project_keys is not None:
            # Mirror the real DAO's DB-side org-scope $in narrowing.
            allowed = set(project_keys)
            matched = [p for p in matched if p.project_key in allowed]
        return matched[offset : offset + limit], len(matched)

    def search_scored(self, query, project_keys):
        # Mirror the real DAO's DB-side filtering: case-insensitive substring on
        # key OR name, and (when provided) narrow to project_keys.
        rows = self._scored_rows
        if project_keys is not None:
            allowed = set(project_keys)
            rows = [r for r in rows if r.project_key in allowed]
        if query:
            needle = query.lower()
            rows = [
                r for r in rows
                if needle in r.project_key.lower() or needle in r.name.lower()
            ]
        return list(rows)

    def get(self, project_key):
        return next((p for p in self._projects if p.project_key == project_key), None)


def _service(projects):
    return DefaultProjectQueryService(FakeProjectsDao(projects), Settings())


SAMPLE = [
    ProjectResponse(project_key="APACHE", name="Apache Server", issue_count=10, open_issue_count=3),
    ProjectResponse(project_key="SPARK", name="Spark Engine", issue_count=5, open_issue_count=1),
    ProjectResponse(project_key="KAFKA", name="Kafka Broker", issue_count=8, open_issue_count=2),
]


def test_search_paginates_and_reports_total() -> None:
    result = _service(SAMPLE).search(SearchProjectsRequest(limit=2, offset=0))
    assert result.page.total == 3
    assert result.page.limit == 2
    assert len(result.items) == 2


def test_search_filters_by_query() -> None:
    result = _service(SAMPLE).search(SearchProjectsRequest(query="kafka"))
    assert [p.project_key for p in result.items] == ["KAFKA"]
    assert result.page.total == 1


def test_get_returns_project() -> None:
    assert _service(SAMPLE).get("SPARK").name == "Spark Engine"


def test_get_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service(SAMPLE).get("NOPE")


# --- scoped, risk-ranked search ------------------------------------------- #

def _row(key, name, *, has_metrics=True, blocker=0, reopen=0.0, aging=0.0,
         critical=0.0, issue=100, open_=10) -> ProjectSearchScoredRow:
    return ProjectSearchScoredRow(
        project_key=key, name=name, open_issue_count=open_, issue_count=issue,
        has_metrics=has_metrics, blocker_count=blocker, reopen_rate=reopen,
        issue_aging_days=aging, critical_defect_ratio=critical)


SCORED_ROWS = [
    # RISKY -> highest composite risk score
    _row("RISKY", "Risky Service", blocker=608, reopen=0.6, aging=2067,
         critical=0.9, issue=1000, open_=1000),
    # MIDDLE -> moderate
    _row("MIDDLE", "Middle Service", blocker=20, reopen=0.3, aging=400,
         critical=0.2, issue=200, open_=80),
    # CALM -> low
    _row("CALM", "Calm Service", blocker=0, reopen=0.0, aging=5.0,
         critical=0.0, issue=100, open_=2),
    # NEW -> no metrics yet (unscored -> null, ranked last)
    _row("NEW", "New Service", has_metrics=False),
]


def _scoped_service(rows=SCORED_ROWS):
    return DefaultProjectQueryService(FakeProjectsDao([], rows), Settings())


def test_scoped_search_ranks_by_risk_desc_nulls_last() -> None:
    result = _scoped_service().search_scoped(
        ScopedProjectSearchRequest(limit=25, offset=0), project_keys=None)
    assert result.total == 4 and result.returned == 4
    keys = [i.project_key for i in result.items]
    assert keys == ["RISKY", "MIDDLE", "CALM", "NEW"]
    # scores strictly descending among scored; NEW is unscored (null) and last.
    assert result.items[0].risk_band == "High"
    assert result.items[-1].project_key == "NEW"
    assert result.items[-1].risk_score is None and result.items[-1].risk_band is None
    assert result.items[0].risk_score > result.items[1].risk_score > result.items[2].risk_score


def test_scoped_search_narrows_to_project_keys() -> None:
    result = _scoped_service().search_scoped(
        ScopedProjectSearchRequest(), project_keys=["CALM"])
    assert result.total == 1
    assert [i.project_key for i in result.items] == ["CALM"]
    assert "RISKY" not in [i.project_key for i in result.items]


def test_scoped_search_q_matches_key_or_name_case_insensitive() -> None:
    # matches on project_key
    by_key = _scoped_service().search_scoped(
        ScopedProjectSearchRequest(query="risky"), project_keys=None)
    assert [i.project_key for i in by_key.items] == ["RISKY"] and by_key.total == 1
    # matches on name (case-insensitive), even when key does not contain it
    by_name = _scoped_service().search_scoped(
        ScopedProjectSearchRequest(query="calm service"), project_keys=None)
    assert [i.project_key for i in by_name.items] == ["CALM"] and by_name.total == 1


def test_scoped_search_paginates_with_total() -> None:
    result = _scoped_service().search_scoped(
        ScopedProjectSearchRequest(limit=2, offset=1), project_keys=None)
    assert result.total == 4 and result.returned == 2
    assert result.offset == 1 and result.limit == 2
    # page 2 of the ranked order: MIDDLE, CALM
    assert [i.project_key for i in result.items] == ["MIDDLE", "CALM"]


def test_scoped_search_limit_clamped_to_100() -> None:
    # request beyond the ceiling is clamped by the service (defensive).
    result = _scoped_service().search_scoped(
        ScopedProjectSearchRequest.model_construct(
            scope=None, query=None, limit=500, offset=0),
        project_keys=None)
    assert result.limit == 100 and result.total == 4 and result.returned == 4


def test_scoped_search_empty_result() -> None:
    result = _scoped_service().search_scoped(
        ScopedProjectSearchRequest(query="no-such-project"), project_keys=None)
    assert result.total == 0 and result.returned == 0 and result.items == []
