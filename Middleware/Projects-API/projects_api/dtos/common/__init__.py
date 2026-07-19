"""Common DTO fragments shared across responses."""
from __future__ import annotations

from projects_api.common.models import TypedModel


class PageMeta(TypedModel):
    """Standard pagination metadata returned with list responses."""

    total: int
    limit: int
    offset: int
