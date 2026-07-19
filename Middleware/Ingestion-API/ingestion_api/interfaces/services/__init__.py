"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion_api.dtos.common import OperationRecord
from ingestion_api.dtos.requests import (
    AcquireDatasetRequest,
    IndexDatasetRequest,
    ReconcileDatasetRequest,
    ReportBatchProgressRequest,
    StartDatasetIngestionRequest,
    StartIngestionRequest,
    UpdateDatasetStatusRequest,
    UpdateRunStatusRequest,
    ValidateDatasetRequest,
)
from ingestion_api.dtos.responses import (
    DatasetStatusResponse,
    IngestionProgressResponse,
    IngestionRunResponse,
)


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


class DatasetService(ABC):
    """Dataset acquisition status + triggering the Airflow download DAG."""

    @abstractmethod
    def get_status(self, dataset_id: str) -> DatasetStatusResponse: ...

    @abstractmethod
    def request_download(self, dataset_id: str) -> DatasetStatusResponse:
        """Trigger the Airflow acquire DAG and mark the dataset DOWNLOADING."""

    @abstractmethod
    def update_status(
        self, dataset_id: str, request: UpdateDatasetStatusRequest
    ) -> DatasetStatusResponse: ...


class DatasetIngestionService(ABC):
    """Batch ingestion of a downloaded dataset into the evidence store."""

    @abstractmethod
    def start(
        self, dataset_id: str, request: StartDatasetIngestionRequest
    ) -> IngestionProgressResponse:
        """Create an ingestion run and trigger the Airflow batch-ingest DAG."""

    @abstractmethod
    def progress(self, dataset_id: str) -> IngestionProgressResponse:
        """Aggregated progress of the latest ingestion run for the dataset."""

    @abstractmethod
    def report_batch(self, run_id: str, request: ReportBatchProgressRequest) -> None:
        """Record a batch checkpoint + progress (called by the ingest DAG)."""

    @abstractmethod
    def finalize_run(self, run_id: str, request: UpdateRunStatusRequest) -> IngestionRunResponse:
        """Set run-level status (called by the ingest DAG)."""

    @abstractmethod
    def committed_batches(self, run_id: str, entity: str) -> list[int]:
        """Batch numbers already committed for (run, entity) — the DAG skips these to resume."""
