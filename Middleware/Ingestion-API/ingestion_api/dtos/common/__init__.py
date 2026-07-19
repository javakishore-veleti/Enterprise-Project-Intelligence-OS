"""Common DTO fragments shared across requests and responses."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from ingestion_api.common.models import TypedModel


class IngestionStatus(StrEnum):
    """Lifecycle states of an ingestion run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class DatasetState(StrEnum):
    NOT_DOWNLOADED = "NOT_DOWNLOADED"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    FAILED = "FAILED"


class OperationRecord(TypedModel):
    """Internal record of an ingestion sub-operation (acquire/validate/index/reconcile)."""

    operation_id: str
    op_type: str
    dataset_id: str
    status: str
    params: dict = {}
    result: dict = {}
    created_at: datetime
    updated_at: datetime
