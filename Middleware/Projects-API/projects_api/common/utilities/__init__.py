"""Genuine cross-cutting utilities (no business logic)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase ``value`` and collapse runs of non-alphanumerics into hyphens.

    Leading/trailing hyphens are trimmed. Returns "" when nothing usable remains.
    """
    return _SLUG_NON_ALNUM.sub("-", value.lower()).strip("-")


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def clamp_page_size(requested: int, default: int, maximum: int) -> int:
    """Bound a caller-supplied page size to the configured maximum."""
    if requested <= 0:
        return default
    return min(requested, maximum)
