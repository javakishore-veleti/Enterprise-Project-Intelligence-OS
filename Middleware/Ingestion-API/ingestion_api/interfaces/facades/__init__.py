"""Abstract facade contracts. Concrete implementations live in ``facades/``.

A facade implements one complete application use case and is what the API
routers depend on.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion_api.dtos.requests import StartIngestionRequest
from ingestion_api.dtos.responses import IngestionRunResponse


class StartIngestionUseCase(ABC):
    @abstractmethod
    def execute(self, request: StartIngestionRequest) -> IngestionRunResponse: ...


class GetIngestionStatusUseCase(ABC):
    @abstractmethod
    def execute(self, run_id: str) -> IngestionRunResponse: ...
