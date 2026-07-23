"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from org_management_api.dtos.common import (
    OrganizationRecord,
    RepositoryGrantRecord,
    RepositoryRecord,
    TrackerProjectRecord,
    UserRecord,
    VisibleProjectRecord,
)
from org_management_api.dtos.requests import (
    AddGrantRequest,
    AddMemberRequest,
    AddTrackerProjectsRequest,
    CreateOrganizationRequest,
    CreateRepositoryRequest,
    CreateUserRequest,
    MoveOrganizationRequest,
    UpdateOrganizationRequest,
    UpdateVisibilityRequest,
)


class OrganizationService(ABC):
    """Reusable business capability: manage the org tree (materialized path)."""

    @abstractmethod
    def create(self, request: CreateOrganizationRequest) -> OrganizationRecord: ...

    @abstractmethod
    def get(self, org_id: str) -> OrganizationRecord: ...

    @abstractmethod
    def children(self, org_id: str) -> list[OrganizationRecord]: ...

    @abstractmethod
    def subtree(self, org_id: str) -> list[OrganizationRecord]: ...

    @abstractmethod
    def ancestors(self, org_id: str) -> list[OrganizationRecord]: ...

    @abstractmethod
    def update(self, org_id: str, request: UpdateOrganizationRequest) -> OrganizationRecord: ...

    @abstractmethod
    def move(self, org_id: str, request: MoveOrganizationRequest) -> OrganizationRecord: ...

    @abstractmethod
    def list_roots(self) -> list[OrganizationRecord]: ...

    @abstractmethod
    def list_tenant(self, root_org_id: str) -> list[OrganizationRecord]: ...


class MembershipService(ABC):
    """Users, memberships, and role assignments."""

    @abstractmethod
    def create_user(self, request: CreateUserRequest) -> UserRecord: ...

    @abstractmethod
    def add_member(
        self, org_id: str, request: AddMemberRequest
    ) -> tuple[UserRecord, list]:
        """Create the user if needed, add membership + roles; return (user, roles)."""

    @abstractmethod
    def list_members(self, org_id: str) -> list[tuple[UserRecord, list]]: ...

    @abstractmethod
    def list_orgs_for_user(self, subject: str) -> list[tuple[OrganizationRecord, list]]: ...


class RepositoryService(ABC):
    """Repositories, tracker projects, visibility, and grants."""

    @abstractmethod
    def create_repository(
        self, org_id: str, request: CreateRepositoryRequest
    ) -> RepositoryRecord: ...

    @abstractmethod
    def add_tracker_projects(
        self, repo_id: str, request: AddTrackerProjectsRequest
    ) -> list[TrackerProjectRecord]: ...

    @abstractmethod
    def set_visibility(
        self, repo_id: str, request: UpdateVisibilityRequest
    ) -> RepositoryRecord: ...

    @abstractmethod
    def add_grant(self, repo_id: str, request: AddGrantRequest) -> RepositoryGrantRecord: ...

    @abstractmethod
    def list_repositories(self, org_id: str) -> list[RepositoryRecord]: ...


class AccessService(ABC):
    """Effective-access resolution over the tenancy graph."""

    @abstractmethod
    def visible_projects_for_subject(self, subject: str) -> list[VisibleProjectRecord]: ...

    @abstractmethod
    def effective_projects_for_org(self, org_id: str) -> list[VisibleProjectRecord]: ...
