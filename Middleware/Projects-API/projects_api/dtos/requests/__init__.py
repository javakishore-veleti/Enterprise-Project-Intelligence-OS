"""Inbound request DTOs (validated at the API boundary)."""
from __future__ import annotations

from pydantic import Field

from projects_api.common.models import TypedModel


class SearchProjectsRequest(TypedModel):
    """Search/filter projects in the evidence store."""

    query: str | None = Field(default=None, description="Case-insensitive match on project key or name.")
    limit: int = Field(default=25, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ScopedProjectSearchRequest(TypedModel):
    """Scale-hardened project search: optional per-user scope + substring query,
    server-side paginated. ``scope`` is a user key; when it resolves to project
    assignments the result is narrowed to those projects (else all projects)."""

    scope: str | None = Field(default=None, description="User key to scope the search to (their assigned projects).")
    query: str | None = Field(default=None, description="Case-insensitive substring match on project key or name.")
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CreateProjectGroupRequest(TypedModel):
    """Create a user-defined group of project keys."""

    name: str = Field(min_length=1, description="Display name; the group_key slug is derived from this.")
    description: str = Field(default="", description="Optional free-text description.")
    project_keys: list[str] = Field(default_factory=list, description="Member project keys.")


class UpdateProjectGroupRequest(TypedModel):
    """Partial update of a project group. Only provided fields are changed."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None)
    project_keys: list[str] | None = Field(default=None)
