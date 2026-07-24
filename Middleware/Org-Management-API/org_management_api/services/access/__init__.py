"""Effective-access resolution service.

Thin service over the AccessDao: the visibility algebra itself is expressed as a
single SQL predicate in the DAO (org/subtree/ancestors/tenant/shared). This is
the query the OTHER services will call in Phase 2 to scope evidence/queries.
"""
from __future__ import annotations

from org_management_api.common.exceptions import NotFoundError
from org_management_api.dtos.common import VisibleProjectPage, VisibleProjectRecord
from org_management_api.interfaces.daos import (
    AccessDao,
    OrganizationsDao,
    UsersDao,
)
from org_management_api.interfaces.services import AccessService


class DefaultAccessService(AccessService):
    def __init__(
        self, access_dao: AccessDao, users_dao: UsersDao, organizations_dao: OrganizationsDao
    ) -> None:
        self._access = access_dao
        self._users = users_dao
        self._orgs = organizations_dao

    def visible_projects_for_subject(self, subject: str) -> list[VisibleProjectRecord]:
        if self._users.get_by_subject(subject) is None:
            raise NotFoundError(f"user '{subject}' not found")
        return self._access.visible_projects_for_subject(subject)

    def visible_projects_for_subject_page(
        self, subject: str, q: str | None, limit: int, offset: int
    ) -> VisibleProjectPage:
        if self._users.get_by_subject(subject) is None:
            raise NotFoundError(f"user '{subject}' not found")
        return self._access.visible_projects_for_subject_page(subject, q, limit, offset)

    def effective_projects_for_org(self, org_id: str) -> list[VisibleProjectRecord]:
        if self._orgs.get(org_id) is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        return self._access.effective_projects_for_org(org_id)

    def effective_projects_for_org_page(
        self, org_id: str, q: str | None, limit: int, offset: int
    ) -> VisibleProjectPage:
        if self._orgs.get(org_id) is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        return self._access.effective_projects_for_org_page(org_id, q, limit, offset)
