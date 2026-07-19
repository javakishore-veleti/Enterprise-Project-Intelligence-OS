"""Inbound request DTOs (validated at the API boundary)."""
from __future__ import annotations

from pydantic import Field

from projects_api.common.models import TypedModel


class SearchProjectsRequest(TypedModel):
    """Search/filter projects in the evidence store."""

    query: str | None = Field(default=None, description="Case-insensitive match on project key or name.")
    limit: int = Field(default=25, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
