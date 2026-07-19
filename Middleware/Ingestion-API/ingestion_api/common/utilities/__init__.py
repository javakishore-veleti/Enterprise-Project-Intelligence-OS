"""Genuine cross-cutting utilities (no business logic)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_id() -> str:
    """Return a fresh opaque identifier."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)
