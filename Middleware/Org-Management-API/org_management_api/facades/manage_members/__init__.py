"""Use case: users, memberships, and role assignments."""
from __future__ import annotations

from org_management_api.dtos.common import (
    OrganizationRecord,
    RoleAssignmentRecord,
    UserRecord,
)
from org_management_api.dtos.requests import AddMemberRequest, CreateUserRequest
from org_management_api.dtos.responses import (
    MemberResponse,
    MembersResponse,
    RoleView,
    UserOrgsResponse,
    UserOrgView,
    UserResponse,
)
from org_management_api.interfaces.services import MembershipService


def _roles(roles: list[RoleAssignmentRecord]) -> list[RoleView]:
    return [RoleView(role=r.role, inherits_down=r.inherits_down) for r in roles]


def _member(user: UserRecord, roles: list[RoleAssignmentRecord]) -> MemberResponse:
    return MemberResponse(
        user_id=user.user_id, subject=user.subject, email=user.email,
        display_name=user.display_name, roles=_roles(roles))


def _user(user: UserRecord) -> UserResponse:
    return UserResponse(
        user_id=user.user_id, subject=user.subject, email=user.email,
        display_name=user.display_name, created_at=user.created_at)


class ManageMembersFacade:
    def __init__(self, service: MembershipService) -> None:
        self._service = service

    def create_user(self, request: CreateUserRequest) -> UserResponse:
        return _user(self._service.create_user(request))

    def add_member(self, org_id: str, request: AddMemberRequest) -> MemberResponse:
        user, roles = self._service.add_member(org_id, request)
        return _member(user, roles)

    def list_members(self, org_id: str) -> MembersResponse:
        rows = self._service.list_members(org_id)
        return MembersResponse(
            org_id=org_id, members=[_member(u, roles) for u, roles in rows])

    def list_orgs_for_user(self, subject: str) -> UserOrgsResponse:
        rows = self._service.list_orgs_for_user(subject)
        orgs = [
            UserOrgView(
                org_id=org.org_id, name=org.name, path=org.path, level=org.level,
                roles=_roles(roles))
            for org, roles in rows
        ]
        return UserOrgsResponse(subject=subject, orgs=orgs)
