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
