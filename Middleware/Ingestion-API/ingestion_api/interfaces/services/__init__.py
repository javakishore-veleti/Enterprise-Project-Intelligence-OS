"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion_api.dtos.common import OperationRecord
from ingestion_api.dtos.requests import (
    AcquireDatasetRequest,
    IndexDatasetRequest,
    ReconcileDatasetRequest,
    StartIngestionRequest,
    ValidateDatasetRequest,
)
from ingestion_api.dtos.responses import IngestionRunResponse


class IngestionOrchestrationService(ABC):
    """Reusable business capability: manage the ingestion-run lifecycle."""

    @abstractmethod
    def start_run(self, request: StartIngestionRequest) -> IngestionRunResponse: ...

    @abstractmethod
    def get_run(self, run_id: str) -> IngestionRunResponse: ...


class OperationsService(ABC):
    """Ingestion sub-operations (acquire/validate/index/reconcile) — synchronous."""

    @abstractmethod
    def acquire(self, request: AcquireDatasetRequest) -> OperationRecord: ...

    @abstractmethod
    def verify_acquisition(self, operation_id: str, expected_sha256: str) -> OperationRecord: ...

    @abstractmethod
    def extract_acquisition(self, operation_id: str) -> OperationRecord: ...

    @abstractmethod
    def validate(self, request: ValidateDatasetRequest) -> OperationRecord: ...

    @abstractmethod
    def create_indexes(self, request: IndexDatasetRequest) -> OperationRecord: ...

    @abstractmethod
    def reconcile(self, request: ReconcileDatasetRequest) -> OperationRecord: ...

    @abstractmethod
    def get(self, operation_id: str, expected_type: str) -> OperationRecord: ...
