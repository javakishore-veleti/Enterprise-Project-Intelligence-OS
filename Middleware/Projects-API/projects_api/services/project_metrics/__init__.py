"""Project metrics service — latest computed delivery-health indicators."""
from __future__ import annotations

from projects_api.common.exceptions import NotFoundError
from projects_api.dtos.responses import ProjectMetricsResponse
from projects_api.interfaces.daos import ProjectMetricsDao
from projects_api.interfaces.services import ProjectMetricsService


class DefaultProjectMetricsService(ProjectMetricsService):
    def __init__(self, metrics_dao: ProjectMetricsDao) -> None:
        self._dao = metrics_dao

    def latest(self, project_key: str) -> ProjectMetricsResponse:
        metrics = self._dao.latest(project_key)
        if metrics is None:
            raise NotFoundError(f"no computed metrics for project '{project_key}'")
        return metrics

    def history(self, project_key: str, limit: int) -> list[ProjectMetricsResponse]:
        return self._dao.history(project_key, limit)
