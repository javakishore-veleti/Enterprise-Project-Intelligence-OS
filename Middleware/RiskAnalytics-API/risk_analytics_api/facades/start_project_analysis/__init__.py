"""Use case: start a risk analysis for a project."""
from __future__ import annotations

from risk_analytics_api.dtos.requests import StartAnalysisRequest
from risk_analytics_api.dtos.responses import AnalysisRunResponse
from risk_analytics_api.interfaces.facades import StartProjectAnalysisUseCase
from risk_analytics_api.interfaces.services import AnalysisOrchestrationService


class StartProjectAnalysisFacade(StartProjectAnalysisUseCase):
    def __init__(self, service: AnalysisOrchestrationService) -> None:
        self._service = service

    def execute(self, project_key: str, request: StartAnalysisRequest) -> AnalysisRunResponse:
        return self._service.run(project_key, request)
