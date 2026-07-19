"""Use case: search projects in the evidence store."""
from __future__ import annotations

from projects_api.dtos.requests import SearchProjectsRequest
from projects_api.dtos.responses import ProjectSearchResponse
from projects_api.interfaces.facades import SearchProjectsUseCase
from projects_api.interfaces.services import ProjectQueryService


class SearchProjectsFacade(SearchProjectsUseCase):
    def __init__(self, service: ProjectQueryService) -> None:
        self._service = service

    def execute(self, request: SearchProjectsRequest) -> ProjectSearchResponse:
        return self._service.search(request)
