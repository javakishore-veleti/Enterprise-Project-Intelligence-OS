"""Genuine cross-cutting utilities (no business logic)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def escape_like(term: str) -> str:
    """Escape LIKE/ILIKE wildcards so user-supplied text matches literally.

    Pair with ``ESCAPE '\\'`` in the SQL predicate (used by the audit search).
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
