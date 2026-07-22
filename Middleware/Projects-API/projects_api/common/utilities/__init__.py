"""Genuine cross-cutting utilities (no business logic)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase ``value`` and collapse runs of non-alphanumerics into hyphens.

    Leading/trailing hyphens are trimmed. Returns "" when nothing usable remains.
    """
    return _SLUG_NON_ALNUM.sub("-", value.lower()).strip("-")


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def end_of_day_utc(day: date) -> datetime:
    """Exclusive upper bound for an as-of date: midnight (UTC) of the day AFTER
    ``day``. Paired with a ``$lt`` comparison this selects every timestamp up to
    and including ``day`` (i.e. ``computed_at <= end-of-day(day)``)."""
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1)


def clamp_page_size(requested: int, default: int, maximum: int) -> int:
    """Bound a caller-supplied page size to the configured maximum."""
    if requested <= 0:
        return default
    return min(requested, maximum)
