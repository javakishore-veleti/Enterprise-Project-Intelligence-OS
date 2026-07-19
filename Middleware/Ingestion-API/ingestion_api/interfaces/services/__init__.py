"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion_api.dtos.requests import StartIngestionRequest
from ingestion_api.dtos.responses import IngestionRunResponse


class IngestionOrchestrationService(ABC):
    """Reusable business capability: manage the ingestion-run lifecycle."""

    @abstractmethod
    def start_run(self, request: StartIngestionRequest) -> IngestionRunResponse: ...

    @abstractmethod
    def get_run(self, run_id: str) -> IngestionRunResponse: ...
