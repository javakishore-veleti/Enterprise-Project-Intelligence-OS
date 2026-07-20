"""Use case: list a project's past analysis runs (history)."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import AnalysisRunListResponse
from risk_analytics_api.interfaces.services import AnalysisOrchestrationService


class ListAnalysisRunsFacade:
    def __init__(self, service: AnalysisOrchestrationService) -> None:
        self._service = service

    def execute(self, project_key: str, limit: int) -> AnalysisRunListResponse:
        return self._service.list_runs(project_key, limit)
