"""Inbound request DTOs (validated at the API boundary)."""
from __future__ import annotations

from pydantic import Field

from ingestion_api.common.models import TypedModel


class StartIngestionRequest(TypedModel):
    """Request to start ingesting a configured dataset."""

    dataset_id: str = Field(..., min_length=1, description="Configured dataset identifier.")
    batch_size: int = Field(default=1000, ge=1, le=100_000, description="Records per batch.")
    parallelism: int = Field(default=4, ge=1, le=64, description="Concurrent batch workers.")
    requested_by: str = Field(default="system", min_length=1)


# --- Operational sub-operations (called by Airflow DAGs over the boundary) ---

class AcquireDatasetRequest(TypedModel):
    dataset_id: str = Field(..., min_length=1)
    source_url: str | None = None
    requested_by: str = Field(default="system", min_length=1)


class VerifyAcquisitionRequest(TypedModel):
    expected_sha256: str = Field(..., min_length=1)


class ValidateDatasetRequest(TypedModel):
    dataset_id: str = Field(..., min_length=1)
    requested_by: str = Field(default="system", min_length=1)
    max_invalid: int = Field(default=0, ge=0)


class IndexDatasetRequest(TypedModel):
    dataset_id: str = Field(..., min_length=1)
    targets: list[str] = Field(default_factory=list)
    requested_by: str = Field(default="system", min_length=1)
    concurrently: bool = True


class ReconcileDatasetRequest(TypedModel):
    dataset_id: str = Field(..., min_length=1)
    requested_by: str = Field(default="system", min_length=1)


class AcquireDatasetTriggerRequest(TypedModel):
    """Request the (Airflow-driven) download of a configured dataset."""

    requested_by: str = Field(default="admin", min_length=1)


class UpdateDatasetStatusRequest(TypedModel):
    """State update posted by the Airflow acquire DAG as it progresses."""

    state: str = Field(..., min_length=1)  # NOT_DOWNLOADED|DOWNLOADING|DOWNLOADED|FAILED
    downloaded_bytes: int | None = Field(default=None, ge=0)
    downloaded_path: str | None = None
    message: str | None = None


class StartDatasetIngestionRequest(TypedModel):
    """Request to (Airflow-driven) batch-ingest a downloaded dataset into Mongo."""

    requested_by: str = Field(default="admin", min_length=1)
    batch_size: int = Field(default=1000, ge=1, le=100_000)
    parallelism: int = Field(default=4, ge=1, le=64)


class ReportBatchProgressRequest(TypedModel):
    """A per-batch checkpoint + progress event posted by the ingest DAG."""

    entity: str = Field(..., min_length=1)
    batch_no: int = Field(..., ge=0)
    source_offset: int = Field(default=0, ge=0)
    record_count: int = Field(default=0, ge=0)
    records_done: int = Field(default=0, ge=0)     # cumulative for this entity
    records_total: int = Field(default=0, ge=0)    # total for this entity
    level: str = "INFO"
    message: str = ""


class UpdateRunStatusRequest(TypedModel):
    """Run-level status finalization posted by the ingest DAG."""

    status: str = Field(..., min_length=1)  # RUNNING|COMPLETED|FAILED
    message: str | None = None
