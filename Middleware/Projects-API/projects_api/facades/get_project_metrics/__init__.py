"""Use case: fetch the latest computed metrics for a project."""
from __future__ import annotations

from projects_api.common.exceptions import NotFoundError
from projects_api.dtos.common import OrgScope
from projects_api.dtos.responses import ProjectMetricsResponse
from projects_api.interfaces.facades import GetProjectMetricsUseCase
from projects_api.interfaces.services import ProjectMetricsService


class GetProjectMetricsFacade(GetProjectMetricsUseCase):
    def __init__(self, service: ProjectMetricsService) -> None:
        self._service = service

    @staticmethod
    def _guard(project_key: str, org_scope: OrgScope | None) -> None:
        # Phase-2: metrics for a project outside the org scope are treated as
        # missing (404, no existence leak).
        if org_scope is not None and not org_scope.allows(project_key):
            raise NotFoundError(f"project '{project_key}' not found")

    def execute(
        self, project_key: str, org_scope: OrgScope | None = None
    ) -> ProjectMetricsResponse:
        self._guard(project_key, org_scope)
        return self._service.latest(project_key)

    def history(
        self, project_key: str, limit: int, org_scope: OrgScope | None = None
    ) -> list[ProjectMetricsResponse]:
        self._guard(project_key, org_scope)
        return self._service.history(project_key, limit)
