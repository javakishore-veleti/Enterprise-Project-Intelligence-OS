"""Genuine cross-cutting utilities (no business logic)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from risk_analytics_api.dtos.common import OrgScope


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def narrow_with_org_scope(
    filter_keys: list[str] | None,
    org_scope: "OrgScope | None",
) -> list[str] | None:
    """AND-compose the Phase-2 org scope onto the existing per-request project
    filter (the ``projects=`` query param that the history/attention DAOs already
    honor).

    ``filter_keys`` is what the existing ``projects=`` filter resolved (``None``
    == no project filter / all projects). ``org_scope`` is the org tenancy scope
    (``None`` == no org headers / org API unreachable).

    - No org scope -> return ``filter_keys`` unchanged (behavior identical to
      before Phase 2).
    - Org scope present, no existing filter -> the org key set becomes the filter.
    - Both present -> intersection (a caller must be allowed by BOTH), preserving
      the existing filter order so pagination stays deterministic.

    A present org scope always yields a concrete list (possibly empty) so the DAO
    applies an authoritative ``project_key = ANY(...)``; an empty result therefore
    means "sees nothing", never "sees everything".
    """
    if org_scope is None:
        return filter_keys
    org_keys = org_scope.as_list()
    if filter_keys is None:
        return org_keys
    allowed = set(org_keys)
    return [key for key in filter_keys if key in allowed]
