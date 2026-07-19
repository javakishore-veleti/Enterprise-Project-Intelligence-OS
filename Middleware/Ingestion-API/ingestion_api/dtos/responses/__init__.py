"""Outbound response DTOs (never expose raw database entities)."""
from __future__ import annotations

from datetime import datetime

from ingestion_api.common.models import TypedModel
from ingestion_api.dtos.common import IngestionStatus


class IngestionRunResponse(TypedModel):
    """Public view of an ingestion run."""

    run_id: str
    dataset_id: str
    status: IngestionStatus
    batch_size: int
    parallelism: int
    requested_by: str
    created_at: datetime
    updated_at: datetime


class HealthResponse(TypedModel):
    """Liveness / readiness payload."""

    status: str
    service: str
    dependencies: dict[str, str] = {}


# --- Operational sub-operation responses (field names match the Airflow DAGs) ---

class AcquisitionResponse(TypedModel):
    acquisition_id: str
    dataset_id: str
    status: str


class AcquisitionVerifyResponse(TypedModel):
    acquisition_id: str
    status: str
    verified: bool
    actual_sha256: str


class AcquisitionExtractResponse(TypedModel):
    acquisition_id: str
    status: str
    extracted: bool
    file_count: int


class ValidationResponse(TypedModel):
    validation_id: str
    dataset_id: str
    status: str
    valid_count: int
    invalid_count: int


class IndexResponse(TypedModel):
    index_job_id: str
    dataset_id: str
    status: str
    indexes_created: int


class ReconciliationResponse(TypedModel):
    reconciliation_id: str
    dataset_id: str
    status: str
    source_count: int
    destination_count: int
    mismatches: list[dict] = []


class EntityProgress(TypedModel):
    entity: str
    records_done: int
    records_total: int
    status: str


class IngestionLogEntry(TypedModel):
    level: str
    entity: str | None
    message: str
    records_done: int
    records_total: int
    created_at: datetime


class IngestionProgressResponse(TypedModel):
    """Aggregated batch-ingestion progress for a dataset (polled by the Admin UI)."""

    run_id: str | None
    dataset_id: str
    status: str  # NOT_STARTED|PENDING|RUNNING|COMPLETED|FAILED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_done: int = 0
    records_total: int = 0
    entities: list[EntityProgress] = []
    recent_log: list[IngestionLogEntry] = []


class DatasetStatusResponse(TypedModel):
    """Acquisition status of a configured dataset (the Initial Dataset feature)."""

    dataset_id: str
    title: str
    state: str
    file_name: str
    source_url: str
    expected_md5: str
    size_bytes: int
    downloaded_bytes: int
    message: str
    zenodo_record: str | None = None
    downloaded_at: datetime | None = None
    updated_at: datetime
