"""Common DTO fragments shared across requests and responses.

These are the typed cross-layer records DAOs return and services consume; they
are never raw database rows and never untyped dicts.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from org_management_api.common.models import TypedModel


class VisibilityScope(StrEnum):
    """How far a repository's tracker_projects are visible from its owning org."""

    ORG = "org"              # owning org only
    SUBTREE = "subtree"      # owning org + all descendants (cascade DOWN)
    ANCESTORS = "ancestors"  # owning org + all ancestors (cascade UP)
    TENANT = "tenant"        # every org under the same root_org_id
    SHARED = "shared"        # explicit repository_grants to another org / tree


class Provider(StrEnum):
    """Supported tracker providers."""

    JIRA = "jira"
    GITHUB = "github"
    AZURE_DEVOPS = "azure_devops"


class GrantDirection(StrEnum):
    """How a `shared` grant cascades to the grantee side."""

    ORG = "org"          # the grantee org only
    SUBTREE = "subtree"  # the grantee org + its descendants


class OrganizationRecord(TypedModel):
    """Internal record of an organization node (materialized-path tree)."""

    org_id: str
    parent_org_id: str | None
    root_org_id: str
    path: str
    depth: int          # 0-indexed (root = 0)
    level: int          # 1-indexed (root = 1 = depth + 1)
    name: str
    kind: str | None = None
    status: str = "active"
    created_at: datetime


class UserRecord(TypedModel):
    """Internal record of a global user identity."""

    user_id: str
    subject: str
    email: str | None = None
    display_name: str | None = None
    created_at: datetime


class RoleAssignmentRecord(TypedModel):
    """A single role a user holds in an org."""

    role: str
    inherits_down: bool = True


class RepositoryRecord(TypedModel):
    """Internal record of a connected tracker account."""

    repo_id: str
    org_id: str
    root_org_id: str
    provider: str
    external_account: str | None = None
    connection_config: dict = {}
    visibility_scope: str = "org"
    created_at: datetime


class TrackerProjectRecord(TypedModel):
    """Internal record of a tracker project under a repository."""

    tracker_project_id: str
    repo_id: str
    external_key: str
    name: str | None = None


class RepositoryGrantRecord(TypedModel):
    """Internal record of an explicit cross-org sharing grant."""

    repo_id: str
    grantee_org_id: str
    direction: str = "org"


class VisibleProjectRecord(TypedModel):
    """A tracker project resolved as visible to a user/org via effective access."""

    external_key: str
    name: str | None
    repo_id: str
    org_id: str
    provider: str
