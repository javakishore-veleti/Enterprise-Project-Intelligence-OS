"""Common DTO fragments."""
from __future__ import annotations

from enum import StrEnum


class AnalysisStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
