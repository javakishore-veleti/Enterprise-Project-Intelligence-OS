"""Use case: (re)compute deterministic project metrics from ingested evidence."""
from __future__ import annotations

from projects_api.dtos.responses import ProjectMetricsResponse
from projects_api.interfaces.services import MetricsComputationService


class ComputeMetricsFacade:
    def __init__(self, service: MetricsComputationService) -> None:
        self._service = service

    def compute(self, project_key: str) -> ProjectMetricsResponse:
        return self._service.compute(project_key)

    def compute_all(self, limit: int) -> list[str]:
        return self._service.compute_all(limit)
