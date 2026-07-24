"""Users, memberships, and role-assignment service."""
from __future__ import annotations

from org_management_api.common.exceptions import NotFoundError
from org_management_api.dtos.common import (
    MemberPage,
    OrganizationRecord,
    RoleAssignmentRecord,
    UserRecord,
)
from org_management_api.dtos.requests import AddMemberRequest, CreateUserRequest
from org_management_api.interfaces.daos import (
    MembersDao,
    OrganizationsDao,
    UsersDao,
)
from org_management_api.interfaces.services import MembershipService


class DefaultMembershipService(MembershipService):
    def __init__(
        self, users_dao: UsersDao, members_dao: MembersDao, organizations_dao: OrganizationsDao
    ) -> None:
        self._users = users_dao
        self._members = members_dao
        self._orgs = organizations_dao

    def create_user(self, request: CreateUserRequest) -> UserRecord:
        return self._users.get_or_create(request.subject, request.email, request.display_name)

    def add_member(
        self, org_id: str, request: AddMemberRequest
    ) -> tuple[UserRecord, list[RoleAssignmentRecord]]:
        if self._orgs.get(org_id) is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        user = self._users.get_or_create(request.subject, request.email, request.display_name)
        self._members.add_membership(user.user_id, org_id)
        roles: list[RoleAssignmentRecord] = []
        for role in request.roles:
            self._members.add_role(user.user_id, org_id, role, request.inherits_down)
            roles.append(RoleAssignmentRecord(role=role, inherits_down=request.inherits_down))
        return user, roles

    def list_members(
        self, org_id: str
    ) -> list[tuple[UserRecord, list[RoleAssignmentRecord]]]:
        if self._orgs.get(org_id) is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        return self._members.list_members(org_id)

    def list_members_page(
        self, org_id: str, q: str | None, role: str | None, limit: int, offset: int
    ) -> MemberPage:
        org = self._orgs.get(org_id)
        if org is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        # Ancestor orgs supply inherited roles (assignments with inherits_down).
        ancestor_ids = [a.org_id for a in self._orgs.ancestors(org.path)]
        return self._members.list_members_page(org_id, q, role, limit, offset, ancestor_ids)

    def list_orgs_for_user(
        self, subject: str
    ) -> list[tuple[OrganizationRecord, list[RoleAssignmentRecord]]]:
        if self._users.get_by_subject(subject) is None:
            raise NotFoundError(f"user '{subject}' not found")
        return self._members.list_orgs_for_user(subject)
