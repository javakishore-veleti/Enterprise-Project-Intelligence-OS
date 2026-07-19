"""Common DTO fragments shared across requests and responses."""
from __future__ import annotations

from enum import StrEnum


class IngestionStatus(StrEnum):
    """Lifecycle states of an ingestion run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
