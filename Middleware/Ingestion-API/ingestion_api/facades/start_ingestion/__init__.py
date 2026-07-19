"""Use case: start a dataset ingestion run."""
from __future__ import annotations

from ingestion_api.dtos.requests import StartIngestionRequest
from ingestion_api.dtos.responses import IngestionRunResponse
from ingestion_api.interfaces.facades import StartIngestionUseCase
from ingestion_api.interfaces.services import IngestionOrchestrationService


class StartIngestionFacade(StartIngestionUseCase):
    def __init__(self, service: IngestionOrchestrationService) -> None:
        self._service = service

    def execute(self, request: StartIngestionRequest) -> IngestionRunResponse:
        return self._service.start_run(request)
