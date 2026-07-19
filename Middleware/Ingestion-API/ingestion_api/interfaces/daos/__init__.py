"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion_api.dtos.common import IngestionStatus, OperationRecord
from ingestion_api.dtos.responses import DatasetStatusResponse, IngestionRunResponse


class IngestionTrackingDao(ABC):
    """Persistence of ingestion-run operational state (PostgreSQL)."""

    @abstractmethod
    def insert_run(self, run: IngestionRunResponse) -> IngestionRunResponse: ...

    @abstractmethod
    def get_run(self, run_id: str) -> IngestionRunResponse | None: ...

    @abstractmethod
    def update_status(self, run_id: str, status: IngestionStatus) -> IngestionRunResponse | None: ...

    @abstractmethod
    def latest_run_for_dataset(self, dataset_id: str) -> IngestionRunResponse | None: ...


class IngestionProgressDao(ABC):
    """Batch checkpoints + progress log (resumable ingestion)."""

    @abstractmethod
    def record_batch(
        self, run_id: str, entity: str, batch_no: int, source_offset: int,
        record_count: int, records_done: int, records_total: int, level: str, message: str,
    ) -> None:
        """Upsert a batch checkpoint and append a progress log entry (idempotent)."""

    @abstractmethod
    def committed_batch_numbers(self, run_id: str, entity: str) -> set[int]:
        """Batch numbers already committed for (run, entity) — used to resume."""

    @abstractmethod
    def entity_progress(self, run_id: str) -> list[tuple[str, int, int]]:
        """Latest (entity, records_done, records_total) per entity."""

    @abstractmethod
    def recent_log(self, run_id: str, limit: int) -> list[tuple]:
        """(level, entity, message, records_done, records_total, created_at), newest first."""


class AirflowGateway(ABC):
    """Gateway that triggers operational workflows in Apache Airflow.

    Agent/reasoning logic never lives here — this only hands ingestion work off
    to the operational scheduler across the governed boundary.
    """

    @abstractmethod
    def trigger_ingestion(self, run_id: str, dataset_id: str) -> str:
        """Trigger the ingestion DAG; return the external run reference."""


class OperationsDao(ABC):
    """Persistence of ingestion sub-operations (PostgreSQL)."""

    @abstractmethod
    def insert(self, record: OperationRecord) -> OperationRecord: ...

    @abstractmethod
    def get(self, operation_id: str) -> OperationRecord | None: ...

    @abstractmethod
    def update_result(self, operation_id: str, status: str, result: dict) -> OperationRecord | None: ...


class DatasetsDao(ABC):
    """Persistence of dataset-acquisition status (PostgreSQL)."""

    @abstractmethod
    def get(self, dataset_id: str) -> DatasetStatusResponse | None: ...

    @abstractmethod
    def update_status(
        self,
        dataset_id: str,
        state: str,
        *,
        downloaded_bytes: int | None = None,
        downloaded_path: str | None = None,
        message: str | None = None,
        set_downloaded_at: bool = False,
    ) -> DatasetStatusResponse | None: ...


class DatasetAcquisitionGateway(ABC):
    """Triggers the Airflow dataset-acquisition DAG (operational scheduler)."""

    @abstractmethod
    def trigger_acquire(self, dataset_id: str) -> str:
        """Trigger the acquire DAG; return the external dag-run reference."""


class DatasetIngestionGateway(ABC):
    """Triggers the Airflow batch-ingestion DAG (operational scheduler)."""

    @abstractmethod
    def trigger_ingest(self, dataset_id: str, run_id: str) -> str:
        """Trigger the ingest DAG for a run; return the external dag-run reference."""


class MetricsComputeGateway(ABC):
    """Triggers the Airflow metric-computation DAG (operational scheduler)."""

    @abstractmethod
    def trigger_compute(self) -> str:
        """Trigger the metrics-compute DAG; return the external dag-run reference."""


class EvidenceCountsGateway(ABC):
    """Read-only counts from the MongoDB evidence store, for validate/index/reconcile."""

    @abstractmethod
    def document_count(self) -> int: ...

    @abstractmethod
    def index_count(self) -> int: ...

    @abstractmethod
    def collection_count(self) -> int: ...
