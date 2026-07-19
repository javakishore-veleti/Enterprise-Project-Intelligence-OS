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
