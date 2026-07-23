"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from org_management_api.dtos.common import (
    OrganizationRecord,
    RepositoryGrantRecord,
    RepositoryRecord,
    RoleAssignmentRecord,
    TrackerProjectRecord,
    UserRecord,
    VisibleProjectRecord,
)


class OrganizationsDao(ABC):
    """Persistence of the organization tree (PostgreSQL, materialized path)."""

    @abstractmethod
    def insert(self, record: OrganizationRecord) -> OrganizationRecord: ...

    @abstractmethod
    def get(self, org_id: str) -> OrganizationRecord | None: ...

    @abstractmethod
    def children(self, org_id: str) -> list[OrganizationRecord]:
        """Direct children of an org (one level down)."""

    @abstractmethod
    def subtree(self, path: str) -> list[OrganizationRecord]:
        """The org at `path` plus all descendants (path-prefix), ordered by path."""

    @abstractmethod
    def ancestors(self, path: str) -> list[OrganizationRecord]:
        """Strict ancestors of the org at `path`, ordered root -> parent."""

    @abstractmethod
    def update(self, org_id: str, name: str, kind: str | None) -> OrganizationRecord | None:
        """Rename / re-kind an org."""

    @abstractmethod
    def list_roots(self) -> list[OrganizationRecord]:
        """All tenant-root orgs (level 1 / no parent)."""

    @abstractmethod
    def list_by_root(self, root_org_id: str) -> list[OrganizationRecord]:
        """Every org in one tenant tree, ordered by path."""

    @abstractmethod
    def reparent(
        self,
        node_id: str,
        new_parent_id: str,
        old_path: str,
        new_path: str,
        new_root_org_id: str,
        depth_delta: int,
        level_delta: int,
    ) -> None:
        """Recompute path/depth/level/root for the node AND all descendants, and
        set the node's parent. Path-prefix rewrite done in a single UPDATE."""


class UsersDao(ABC):
    """Persistence of global user identities (PostgreSQL)."""

    @abstractmethod
    def get_or_create(
        self, subject: str, email: str | None, display_name: str | None
    ) -> UserRecord:
        """Return the existing user for `subject`, else create it."""

    @abstractmethod
    def get_by_subject(self, subject: str) -> UserRecord | None: ...


class MembersDao(ABC):
    """Persistence of memberships + role assignments (PostgreSQL)."""

    @abstractmethod
    def add_membership(self, user_id: str, org_id: str) -> None:
        """Idempotent add of a user to an org."""

    @abstractmethod
    def add_role(self, user_id: str, org_id: str, role: str, inherits_down: bool) -> None:
        """Idempotent add of a role for a user in an org."""

    @abstractmethod
    def list_members(
        self, org_id: str
    ) -> list[tuple[UserRecord, list[RoleAssignmentRecord]]]:
        """Members of an org, each with the roles they hold there."""

    @abstractmethod
    def list_orgs_for_user(
        self, subject: str
    ) -> list[tuple[OrganizationRecord, list[RoleAssignmentRecord]]]:
        """Orgs a user belongs to, each with the roles they hold there."""


class RepositoriesDao(ABC):
    """Persistence of repositories, tracker projects, and grants (PostgreSQL)."""

    @abstractmethod
    def insert_repo(self, record: RepositoryRecord) -> RepositoryRecord: ...

    @abstractmethod
    def get_repo(self, repo_id: str) -> RepositoryRecord | None: ...

    @abstractmethod
    def list_by_org(self, org_id: str) -> list[RepositoryRecord]: ...

    @abstractmethod
    def update_visibility(self, repo_id: str, visibility_scope: str) -> RepositoryRecord | None: ...

    @abstractmethod
    def insert_tracker_projects(
        self, repo_id: str, projects: list[tuple[str, str | None]]
    ) -> list[TrackerProjectRecord]:
        """Idempotent upsert of (external_key, name) tracker projects under a repo."""

    @abstractmethod
    def list_tracker_projects(self, repo_id: str) -> list[TrackerProjectRecord]: ...

    @abstractmethod
    def add_grant(
        self, repo_id: str, grantee_org_id: str, direction: str
    ) -> RepositoryGrantRecord:
        """Idempotent add of a cross-org sharing grant."""


class AccessDao(ABC):
    """Effective-access resolution (the tenancy query surface, PostgreSQL)."""

    @abstractmethod
    def visible_projects_for_subject(self, subject: str) -> list[VisibleProjectRecord]:
        """Union of tracker projects visible to ANY org the user is a member of."""

    @abstractmethod
    def effective_projects_for_org(self, org_id: str) -> list[VisibleProjectRecord]:
        """Tracker projects visible from a single org context."""
