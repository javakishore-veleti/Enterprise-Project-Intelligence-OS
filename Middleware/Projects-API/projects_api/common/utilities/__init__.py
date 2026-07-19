"""Genuine cross-cutting utilities (no business logic)."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def clamp_page_size(requested: int, default: int, maximum: int) -> int:
    """Bound a caller-supplied page size to the configured maximum."""
    if requested <= 0:
        return default
    return min(requested, maximum)
