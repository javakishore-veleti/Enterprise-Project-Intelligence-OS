"""Inbound request DTOs (validated at the API boundary)."""
from __future__ import annotations

from pydantic import Field

from org_management_api.common.models import TypedModel
from org_management_api.dtos.common import GrantDirection, Provider, VisibilityScope


# --- Organizations ---

class CreateOrganizationRequest(TypedModel):
    """Create an org. With `parent_org_id` it is a sub-branch (root/path/depth/
    level derived from the parent); without it, a brand-new root/tenant."""

    name: str = Field(..., min_length=1)
    parent_org_id: str | None = None
    kind: str | None = None


class UpdateOrganizationRequest(TypedModel):
    """Rename / re-kind an org (structure unchanged)."""

    name: str | None = Field(default=None, min_length=1)
    kind: str | None = None


class MoveOrganizationRequest(TypedModel):
    """Reparent an org (and its whole subtree) under a new parent."""

    new_parent_org_id: str = Field(..., min_length=1)


# --- Users / membership / roles ---

class CreateUserRequest(TypedModel):
    subject: str = Field(..., min_length=1)
    email: str | None = None
    display_name: str | None = None


class AddMemberRequest(TypedModel):
    """Add a user (created if unknown) to an org with one or more roles."""

    subject: str = Field(..., min_length=1)
    roles: list[str] = Field(default_factory=list)
    inherits_down: bool = True
    email: str | None = None
    display_name: str | None = None


# --- Repositories / tracker projects / grants ---

class CreateRepositoryRequest(TypedModel):
    provider: Provider
    external_account: str | None = None
    visibility_scope: VisibilityScope = VisibilityScope.ORG
    connection_config: dict = Field(default_factory=dict)


class TrackerProjectInput(TypedModel):
    external_key: str = Field(..., min_length=1)
    name: str | None = None


class AddTrackerProjectsRequest(TypedModel):
    """Add one or more tracker projects to a repository (bulk ok)."""

    projects: list[TrackerProjectInput] = Field(..., min_length=1)


class UpdateVisibilityRequest(TypedModel):
    visibility_scope: VisibilityScope


class AddGrantRequest(TypedModel):
    grantee_org_id: str = Field(..., min_length=1)
    direction: GrantDirection = GrantDirection.ORG
