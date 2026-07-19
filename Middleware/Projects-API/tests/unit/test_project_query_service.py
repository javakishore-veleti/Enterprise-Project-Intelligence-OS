"""Unit tests for the project query service against an in-memory fake DAO."""
from __future__ import annotations

import pytest

from projects_api.common.configuration import Settings
from projects_api.common.exceptions import NotFoundError
from projects_api.dtos.requests import SearchProjectsRequest
from projects_api.dtos.responses import ProjectResponse
from projects_api.interfaces.daos import ProjectsDao
from projects_api.services.project_query import DefaultProjectQueryService


class FakeProjectsDao(ProjectsDao):
    def __init__(self, projects: list[ProjectResponse]) -> None:
        self._projects = projects

    def search(self, query, limit, offset):
        matched = [
            p for p in self._projects
            if not query or query.lower() in p.project_key.lower() or query.lower() in p.name.lower()
        ]
        return matched[offset : offset + limit], len(matched)

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
