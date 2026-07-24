"""Genuine cross-cutting utilities (no business logic)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_id() -> str:
    """Return a fresh opaque identifier (uuid4 string)."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def escape_like(term: str) -> str:
    """Escape LIKE/ILIKE wildcards so user-supplied text is matched literally.

    Pair the result with ``ESCAPE '\\'`` in the SQL predicate. Used by the org
    search + member search filters so ``%`` / ``_`` in input are not wildcards.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
