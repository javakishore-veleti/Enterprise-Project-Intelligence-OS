"""Use case: fetch a single project by key."""
from __future__ import annotations

from projects_api.dtos.responses import ProjectResponse
from projects_api.interfaces.facades import GetProjectUseCase
from projects_api.interfaces.services import ProjectQueryService


class GetProjectFacade(GetProjectUseCase):
    def __init__(self, service: ProjectQueryService) -> None:
        self._service = service

    def execute(self, project_key: str) -> ProjectResponse:
        return self._service.get(project_key)
