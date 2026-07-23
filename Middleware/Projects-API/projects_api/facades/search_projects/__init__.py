"""Use case: search projects in the evidence store."""
from __future__ import annotations

from projects_api.dtos.common import OrgScope
from projects_api.dtos.requests import SearchProjectsRequest
from projects_api.dtos.responses import ProjectSearchResponse
from projects_api.interfaces.facades import SearchProjectsUseCase
from projects_api.interfaces.services import ProjectQueryService


class SearchProjectsFacade(SearchProjectsUseCase):
    def __init__(self, service: ProjectQueryService) -> None:
        self._service = service

    def execute(
        self,
        request: SearchProjectsRequest,
        org_scope: OrgScope | None = None,
    ) -> ProjectSearchResponse:
        # Phase-2: the plain list has no legacy per-user scope, so the org scope
        # (when present) is the sole $in narrowing; empty -> empty results.
        project_keys = org_scope.as_list() if org_scope is not None else None
        return self._service.search(request, project_keys)
