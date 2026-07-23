"""Genuine cross-cutting utilities (no business logic)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from projects_api.dtos.common import OrgScope

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


def narrow_with_org_scope(
    assignment_keys: list[str] | None,
    org_scope: "OrgScope | None",
) -> list[str] | None:
    """AND-compose the Phase-2 org scope onto the existing per-user scope.

    ``assignment_keys`` is what the legacy ``X-User-Key`` / ``scope`` seam
    resolved (``None`` == unscoped / all projects). ``org_scope`` is the org
    tenancy scope (``None`` == no org headers / org API unreachable).

    - No org scope -> return ``assignment_keys`` unchanged (behavior identical to
      before Phase 2).
    - Org scope present, no legacy scope -> the org key set becomes the scope.
    - Both present -> intersection (a caller must be allowed by BOTH), preserving
      the legacy order so ranking/pagination stay deterministic.

    A present org scope always yields a concrete list (possibly empty) so the DAO
    applies an authoritative ``$in``; an empty result therefore means "sees
    nothing", never "sees everything".
    """
    if org_scope is None:
        return assignment_keys
    org_keys = org_scope.as_list()
    if assignment_keys is None:
        return org_keys
    allowed = set(org_keys)
    return [key for key in assignment_keys if key in allowed]
