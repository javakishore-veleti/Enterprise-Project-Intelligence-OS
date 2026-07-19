"""Use case: fetch an analysis run and its findings."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import AnalysisRunResponse
from risk_analytics_api.interfaces.facades import GetAnalysisRunUseCase
from risk_analytics_api.interfaces.services import AnalysisOrchestrationService


class GetAnalysisRunFacade(GetAnalysisRunUseCase):
    def __init__(self, service: AnalysisOrchestrationService) -> None:
        self._service = service

    def execute(self, run_id: str) -> AnalysisRunResponse:
        return self._service.get_run(run_id)
