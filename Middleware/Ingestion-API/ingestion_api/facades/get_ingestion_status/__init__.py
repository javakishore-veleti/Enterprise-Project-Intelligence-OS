"""Use case: get the status of an ingestion run."""
from __future__ import annotations

from ingestion_api.dtos.responses import IngestionRunResponse
from ingestion_api.interfaces.facades import GetIngestionStatusUseCase
from ingestion_api.interfaces.services import IngestionOrchestrationService


class GetIngestionStatusFacade(GetIngestionStatusUseCase):
    def __init__(self, service: IngestionOrchestrationService) -> None:
        self._service = service

    def execute(self, run_id: str) -> IngestionRunResponse:
        return self._service.get_run(run_id)
