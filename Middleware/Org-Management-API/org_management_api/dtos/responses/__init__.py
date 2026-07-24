"""Outbound response DTOs (never expose raw database entities)."""
from __future__ import annotations

from datetime import datetime

from org_management_api.common.models import TypedModel


class HealthResponse(TypedModel):
    """Liveness / readiness payload."""

    status: str
    service: str
    dependencies: dict[str, str] = {}


# --- Organizations ---

class OrganizationResponse(TypedModel):
    """Public view of an organization node."""

    org_id: str
    parent_org_id: str | None
    root_org_id: str
    path: str
    depth: int          # 0-indexed (root = 0)
    level: int          # 1-indexed (root = 1 = depth + 1)
    name: str
    kind: str | None = None
    status: str
    created_at: datetime
    # Cheap counters so a UI can show an expand chevron + counts WITHOUT
    # fetching children/members. Default 0 (populated on read where computed).
    child_count: int = 0
    member_count: int = 0


class OrganizationListResponse(TypedModel):
    """A list of orgs. For the paginated reads (children, search) the paging
    fields are populated; for the unpaged reads (subtree, ancestors, roots)
    they stay ``None`` so existing callers are unaffected."""

    organizations: list[OrganizationResponse] = []
    total: int | None = None
    returned: int | None = None
    offset: int | None = None
    limit: int | None = None


class OrgStatsResponse(TypedModel):
    """Cheap tenancy aggregate counts (COUNT queries only — never a subtree
    fetch). Powers the dashboard org summary. ``root`` scopes to one tenant."""

    total_orgs: int
    root_count: int
    total_members: int
    total_repositories: int


# --- Users / membership / roles ---

class RoleView(TypedModel):
    role: str
    inherits_down: bool


class InheritedRoleView(TypedModel):
    """A role that applies to a member via an ancestor org (inherited down)."""

    role: str
    source_org_id: str
    source_org_name: str
    source_org_level: int


class UserResponse(TypedModel):
    user_id: str
    subject: str
    email: str | None = None
    display_name: str | None = None
    created_at: datetime


class MemberResponse(TypedModel):
    """A member of an org: identity + the roles they hold in that org.

    ``roles`` / ``direct_roles`` are the DIRECT role_assignments in this org
    (``roles`` retained for backward compatibility); ``inherited_roles`` are the
    roles that apply here via an ancestor org (``inherits_down = true``)."""

    user_id: str
    subject: str
    email: str | None = None
    display_name: str | None = None
    roles: list[RoleView] = []
    direct_roles: list[RoleView] = []
    inherited_roles: list[InheritedRoleView] = []


class MembersResponse(TypedModel):
    """Members of an org. The paging fields are populated by the paginated list
    endpoint; ``None`` when unset."""

    org_id: str
    members: list[MemberResponse] = []
    total: int | None = None
    returned: int | None = None
    offset: int | None = None
    limit: int | None = None


class UserOrgView(TypedModel):
    """One org a user belongs to, with the roles they hold there."""

    org_id: str
    name: str
    path: str
    level: int
    roles: list[RoleView] = []


class UserOrgsResponse(TypedModel):
    subject: str
    orgs: list[UserOrgView] = []


class RolesResponse(TypedModel):
    """Distinct role names for a role-picker typeahead. ``roles`` is capped;
    ``total`` is the total number of distinct roles matching the query."""

    roles: list[str] = []
    total: int = 0


# --- Repositories / tracker projects / grants ---

class RepositoryResponse(TypedModel):
    repo_id: str
    org_id: str
    root_org_id: str
    provider: str
    external_account: str | None = None
    connection_config: dict = {}
    visibility_scope: str
    created_at: datetime


class RepositoriesResponse(TypedModel):
    """Repositories under an org. Paging fields are populated by the paginated
    list endpoint (``q`` / ``limit`` / ``offset``); ``None`` when unset so the
    default (no-param) call is unchanged."""

    org_id: str
    repositories: list[RepositoryResponse] = []
    total: int | None = None
    returned: int | None = None
    offset: int | None = None
    limit: int | None = None


class TrackerProjectResponse(TypedModel):
    tracker_project_id: str
    repo_id: str
    external_key: str
    name: str | None = None


class TrackerProjectsResponse(TypedModel):
    """Tracker projects under a repo. Paging fields populated by the paginated
    LIST endpoint; ``None`` on the (create) response so that stays unchanged."""

    repo_id: str
    projects: list[TrackerProjectResponse] = []
    total: int | None = None
    returned: int | None = None
    offset: int | None = None
    limit: int | None = None


class GrantResponse(TypedModel):
    repo_id: str
    grantee_org_id: str
    direction: str


class GrantsResponse(TypedModel):
    """A page of cross-org sharing grants on a repo."""

    repo_id: str
    grants: list[GrantResponse] = []
    total: int | None = None
    returned: int | None = None
    offset: int | None = None
    limit: int | None = None


# --- Effective access resolution ---

class VisibleProjectResponse(TypedModel):
    external_key: str
    name: str | None = None
    repo_id: str
    org_id: str
    provider: str


class VisibleProjectsResponse(TypedModel):
    """A subject's visible tracker projects. Paging fields populated when the
    caller pages/searches (``q`` / ``limit`` / ``offset``); ``None`` otherwise
    so the existing no-param call is unchanged."""

    subject: str
    projects: list[VisibleProjectResponse] = []
    total: int | None = None
    returned: int | None = None
    offset: int | None = None
    limit: int | None = None


class EffectiveProjectsResponse(TypedModel):
    """An org's effective (visible) tracker projects, with the same optional
    paging envelope as ``VisibleProjectsResponse``."""

    org_id: str
    projects: list[VisibleProjectResponse] = []
    total: int | None = None
    returned: int | None = None
    offset: int | None = None
    limit: int | None = None
