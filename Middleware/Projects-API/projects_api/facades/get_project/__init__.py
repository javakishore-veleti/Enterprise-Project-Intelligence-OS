"""Use case: fetch a single project by key."""
from __future__ import annotations

from projects_api.common.exceptions import NotFoundError
from projects_api.dtos.common import OrgScope
from projects_api.dtos.responses import ProjectResponse
from projects_api.interfaces.facades import GetProjectUseCase
from projects_api.interfaces.services import ProjectQueryService


class GetProjectFacade(GetProjectUseCase):
    def __init__(self, service: ProjectQueryService) -> None:
        self._service = service

    def execute(
        self, project_key: str, org_scope: OrgScope | None = None
    ) -> ProjectResponse:
        # Phase-2: a project outside the caller's org scope is indistinguishable
        # from a missing one (404, no existence leak).
        if org_scope is not None and not org_scope.allows(project_key):
            raise NotFoundError(f"project '{project_key}' not found")
        return self._service.get(project_key)
