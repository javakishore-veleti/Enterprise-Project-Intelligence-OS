"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ingestion_api.dtos.common import IngestionStatus, OperationRecord
from ingestion_api.dtos.responses import (
    DatasetStatusResponse,
    IngestionRunResponse,
    SyncBatchInfo,
    SyncProjectProgress,
)


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
    def trigger_ingest(self, dataset_id: str, run_id: str, repos: list[str] | None = None) -> str:
        """Trigger the ingest DAG for a run; return the external dag-run reference.

        ``repos`` optionally limits ingestion to specific Jira repos (bounded ingest).
        """


class MetricsComputeGateway(ABC):
    """Triggers the Airflow metric-computation DAG (operational scheduler)."""

    @abstractmethod
    def trigger_compute(self) -> str:
        """Trigger the metrics-compute DAG; return the external dag-run reference."""


class TrackerSyncGateway(ABC):
    """Triggers the Airflow ``tracker_repository_sync`` DAG (operational scheduler).

    The generated ``sync_run_id`` is passed as the Airflow ``dag_run_id`` so the
    DAG run and the tracking rows share one id.
    """

    @abstractmethod
    def trigger_sync(self, sync_run_id: str, conf: dict) -> str:
        """Trigger the sync DAG with ``dag_run_id == sync_run_id``; return the ref."""


class SyncTrackingDao(ABC):
    """Persistence of tracker-sync tracking log (run / project / batch) — PostgreSQL."""

    @abstractmethod
    def insert_run(
        self, sync_run_id: str, repo_id: str, org_id: str, root_org_id: str,
        provider: str, since: datetime | None, requested_by: str,
    ) -> None: ...

    @abstractmethod
    def get_run(self, sync_run_id: str) -> dict | None:
        """Raw run row as a dict, or None."""

    @abstractmethod
    def latest_run_for_repo(self, repo_id: str) -> dict | None: ...

    @abstractmethod
    def last_completed_watermark(self, repo_id: str) -> datetime | None:
        """``started_at`` of the most recent COMPLETED run for the repo (delta base)."""

    @abstractmethod
    def set_run_projects(
        self, sync_run_id: str, projects_intended: list[str], projects_considered: int
    ) -> None: ...

    @abstractmethod
    def upsert_project_plan(
        self, sync_run_id: str, project_key: str, issues_intended: int, batches_total: int
    ) -> None:
        """Create/refresh a project row IN_PROGRESS with its planned totals."""

    @abstractmethod
    def committed_batch_numbers(self, sync_run_id: str, project_key: str) -> set[int]: ...

    @abstractmethod
    def commit_batch(
        self, sync_run_id: str, project_key: str, batch_no: int,
        source_offset: int, record_count: int,
    ) -> None:
        """Idempotently record a batch + atomically bump project counters; flip
        the project to COMPLETED when its last batch lands."""

    @abstractmethod
    def finalize_run(self, sync_run_id: str, status: str, message: str | None) -> dict | None:
        """Reconcile run status from project rollups; return the updated run row."""

    @abstractmethod
    def project_progress(self, sync_run_id: str) -> list[SyncProjectProgress]: ...

    @abstractmethod
    def recent_batches(self, sync_run_id: str, limit: int) -> list[SyncBatchInfo]: ...


class EvidenceCountsGateway(ABC):
    """Read-only counts from the MongoDB evidence store, for validate/index/reconcile."""

    @abstractmethod
    def document_count(self) -> int: ...

    @abstractmethod
    def index_count(self) -> int: ...

    @abstractmethod
    def collection_count(self) -> int: ...
