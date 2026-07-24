"""Repositories, tracker projects, visibility, and grants service."""
from __future__ import annotations

from org_management_api.common.exceptions import NotFoundError
from org_management_api.common.utilities import new_id, utc_now
from org_management_api.dtos.common import (
    GrantPage,
    RepositoryGrantRecord,
    RepositoryPage,
    RepositoryRecord,
    TrackerProjectPage,
    TrackerProjectRecord,
)
from org_management_api.dtos.requests import (
    AddGrantRequest,
    AddTrackerProjectsRequest,
    CreateRepositoryRequest,
    UpdateVisibilityRequest,
)
from org_management_api.interfaces.daos import OrganizationsDao, RepositoriesDao
from org_management_api.interfaces.services import RepositoryService


class DefaultRepositoryService(RepositoryService):
    def __init__(
        self, repositories_dao: RepositoriesDao, organizations_dao: OrganizationsDao
    ) -> None:
        self._repos = repositories_dao
        self._orgs = organizations_dao

    def _require_repo(self, repo_id: str) -> RepositoryRecord:
        repo = self._repos.get_repo(repo_id)
        if repo is None:
            raise NotFoundError(f"repository '{repo_id}' not found")
        return repo

    def create_repository(
        self, org_id: str, request: CreateRepositoryRequest
    ) -> RepositoryRecord:
        org = self._orgs.get(org_id)
        if org is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        record = RepositoryRecord(
            repo_id=new_id(),
            org_id=org_id,
            root_org_id=org.root_org_id,
            provider=str(request.provider),
            external_account=request.external_account,
            connection_config=dict(request.connection_config),
            visibility_scope=str(request.visibility_scope),
            created_at=utc_now(),
        )
        return self._repos.insert_repo(record)

    def add_tracker_projects(
        self, repo_id: str, request: AddTrackerProjectsRequest
    ) -> list[TrackerProjectRecord]:
        self._require_repo(repo_id)
        projects = [(p.external_key, p.name) for p in request.projects]
        return self._repos.insert_tracker_projects(repo_id, projects)

    def set_visibility(
        self, repo_id: str, request: UpdateVisibilityRequest
    ) -> RepositoryRecord:
        self._require_repo(repo_id)
        updated = self._repos.update_visibility(repo_id, str(request.visibility_scope))
        if updated is None:  # pragma: no cover - guarded by _require_repo
            raise NotFoundError(f"repository '{repo_id}' not found")
        return updated

    def add_grant(self, repo_id: str, request: AddGrantRequest) -> RepositoryGrantRecord:
        self._require_repo(repo_id)
        if self._orgs.get(request.grantee_org_id) is None:
            raise NotFoundError(f"organization '{request.grantee_org_id}' not found")
        return self._repos.add_grant(
            repo_id, request.grantee_org_id, str(request.direction))

    def list_repositories(self, org_id: str) -> list[RepositoryRecord]:
        if self._orgs.get(org_id) is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        return self._repos.list_by_org(org_id)

    def list_repositories_page(
        self, org_id: str, q: str | None, limit: int, offset: int
    ) -> RepositoryPage:
        if self._orgs.get(org_id) is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        return self._repos.list_by_org_page(org_id, q, limit, offset)

    def list_tracker_projects_page(
        self, repo_id: str, q: str | None, limit: int, offset: int
    ) -> TrackerProjectPage:
        self._require_repo(repo_id)
        return self._repos.list_tracker_projects_page(repo_id, q, limit, offset)

    def list_grants_page(
        self, repo_id: str, limit: int, offset: int
    ) -> GrantPage:
        self._require_repo(repo_id)
        return self._repos.list_grants_page(repo_id, limit, offset)
