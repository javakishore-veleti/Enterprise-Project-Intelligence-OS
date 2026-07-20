"""Use case: fetch the latest computed metrics for a project."""
from __future__ import annotations

from projects_api.dtos.responses import ProjectMetricsResponse
from projects_api.interfaces.facades import GetProjectMetricsUseCase
from projects_api.interfaces.services import ProjectMetricsService


class GetProjectMetricsFacade(GetProjectMetricsUseCase):
    def __init__(self, service: ProjectMetricsService) -> None:
        self._service = service

    def execute(self, project_key: str) -> ProjectMetricsResponse:
        return self._service.latest(project_key)

    def history(self, project_key: str, limit: int) -> list[ProjectMetricsResponse]:
        return self._service.history(project_key, limit)
