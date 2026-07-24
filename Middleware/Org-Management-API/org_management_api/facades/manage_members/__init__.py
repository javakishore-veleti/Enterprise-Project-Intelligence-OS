"""Use case: users, memberships, and role assignments."""
from __future__ import annotations

from org_management_api.dtos.common import (
    InheritedRoleRecord,
    MemberRecord,
    OrganizationRecord,
    RoleAssignmentRecord,
    UserRecord,
)
from org_management_api.dtos.requests import AddMemberRequest, CreateUserRequest
from org_management_api.dtos.responses import (
    InheritedRoleView,
    MemberResponse,
    MembersResponse,
    RolesResponse,
    RoleView,
    UserOrgsResponse,
    UserOrgView,
    UserResponse,
)
from org_management_api.interfaces.services import MembershipService


def _roles(roles: list[RoleAssignmentRecord]) -> list[RoleView]:
    return [RoleView(role=r.role, inherits_down=r.inherits_down) for r in roles]


def _inherited(roles: list[InheritedRoleRecord]) -> list[InheritedRoleView]:
    return [
        InheritedRoleView(
            role=r.role, source_org_id=r.source_org_id,
            source_org_name=r.source_org_name, source_org_level=r.source_org_level)
        for r in roles
    ]


def _member(user: UserRecord, roles: list[RoleAssignmentRecord]) -> MemberResponse:
    views = _roles(roles)
    return MemberResponse(
        user_id=user.user_id, subject=user.subject, email=user.email,
        display_name=user.display_name, roles=views, direct_roles=views)


def _member_row(rec: MemberRecord) -> MemberResponse:
    direct = _roles(rec.direct_roles)
    return MemberResponse(
        user_id=rec.user.user_id, subject=rec.user.subject, email=rec.user.email,
        display_name=rec.user.display_name, roles=direct, direct_roles=direct,
        inherited_roles=_inherited(rec.inherited_roles))


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

    def list_members_page(
        self, org_id: str, q: str | None, role: str | None, limit: int, offset: int
    ) -> MembersResponse:
        page = self._service.list_members_page(org_id, q, role, limit, offset)
        members = [_member_row(r) for r in page.members]
        return MembersResponse(
            org_id=org_id, members=members, total=page.total,
            returned=len(members), offset=page.offset, limit=page.limit)

    def list_roles(self, q: str | None, limit: int) -> RolesResponse:
        page = self._service.list_roles(q, limit)
        return RolesResponse(roles=page.roles, total=page.total)

    def list_orgs_for_user(self, subject: str) -> UserOrgsResponse:
        rows = self._service.list_orgs_for_user(subject)
        orgs = [
            UserOrgView(
                org_id=org.org_id, name=org.name, path=org.path, level=org.level,
                roles=_roles(roles))
            for org, roles in rows
        ]
        return UserOrgsResponse(subject=subject, orgs=orgs)
