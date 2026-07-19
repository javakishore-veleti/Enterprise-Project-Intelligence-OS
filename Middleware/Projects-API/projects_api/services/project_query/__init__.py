"""Project query service — search and fetch projects from the evidence store."""
from __future__ import annotations

from projects_api.common.configuration import Settings
from projects_api.common.exceptions import NotFoundError
from projects_api.common.utilities import clamp_page_size
from projects_api.dtos.common import PageMeta
from projects_api.dtos.requests import SearchProjectsRequest
from projects_api.dtos.responses import ProjectResponse, ProjectSearchResponse
from projects_api.interfaces.daos import ProjectsDao
from projects_api.interfaces.services import ProjectQueryService


class DefaultProjectQueryService(ProjectQueryService):
    def __init__(self, projects_dao: ProjectsDao, settings: Settings) -> None:
        self._dao = projects_dao
        self._settings = settings

    def search(self, request: SearchProjectsRequest) -> ProjectSearchResponse:
        limit = clamp_page_size(
            request.limit, self._settings.default_page_size, self._settings.max_page_size
        )
        items, total = self._dao.search(request.query, limit, request.offset)
        return ProjectSearchResponse(
            items=items,
            page=PageMeta(total=total, limit=limit, offset=request.offset),
        )

    def get(self, project_key: str) -> ProjectResponse:
        project = self._dao.get(project_key)
        if project is None:
            raise NotFoundError(f"project '{project_key}' not found")
        return project
