"""Use case: repositories, tracker projects, visibility, and grants."""
from __future__ import annotations

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
from org_management_api.dtos.responses import (
    GrantResponse,
    GrantsResponse,
    RepositoriesResponse,
    RepositoryResponse,
    TrackerProjectResponse,
    TrackerProjectsResponse,
)
from org_management_api.interfaces.services import RepositoryService


def _repo(rec: RepositoryRecord) -> RepositoryResponse:
    return RepositoryResponse(
        repo_id=rec.repo_id, org_id=rec.org_id, root_org_id=rec.root_org_id,
        provider=rec.provider, external_account=rec.external_account,
        connection_config=rec.connection_config, visibility_scope=rec.visibility_scope,
        created_at=rec.created_at)


def _tp(rec: TrackerProjectRecord) -> TrackerProjectResponse:
    return TrackerProjectResponse(
        tracker_project_id=rec.tracker_project_id, repo_id=rec.repo_id,
        external_key=rec.external_key, name=rec.name)


class ManageRepositoriesFacade:
    def __init__(self, service: RepositoryService) -> None:
        self._service = service

    def create_repository(
        self, org_id: str, request: CreateRepositoryRequest
    ) -> RepositoryResponse:
        return _repo(self._service.create_repository(org_id, request))

    def add_tracker_projects(
        self, repo_id: str, request: AddTrackerProjectsRequest
    ) -> TrackerProjectsResponse:
        created = self._service.add_tracker_projects(repo_id, request)
        return TrackerProjectsResponse(repo_id=repo_id, projects=[_tp(p) for p in created])

    def set_visibility(
        self, repo_id: str, request: UpdateVisibilityRequest
    ) -> RepositoryResponse:
        return _repo(self._service.set_visibility(repo_id, request))

    def add_grant(self, repo_id: str, request: AddGrantRequest) -> GrantResponse:
        grant: RepositoryGrantRecord = self._service.add_grant(repo_id, request)
        return GrantResponse(
            repo_id=grant.repo_id, grantee_org_id=grant.grantee_org_id,
            direction=grant.direction)

    def list_repositories(
        self, org_id: str, q: str | None = None, limit: int = 50, offset: int = 0
    ) -> RepositoriesResponse:
        page: RepositoryPage = self._service.list_repositories_page(org_id, q, limit, offset)
        return RepositoriesResponse(
            org_id=org_id,
            repositories=[_repo(r) for r in page.repositories],
            total=page.total,
            returned=len(page.repositories),
            offset=page.offset,
            limit=page.limit,
        )

    def list_tracker_projects(
        self, repo_id: str, q: str | None = None, limit: int = 50, offset: int = 0
    ) -> TrackerProjectsResponse:
        page: TrackerProjectPage = self._service.list_tracker_projects_page(
            repo_id, q, limit, offset)
        return TrackerProjectsResponse(
            repo_id=repo_id,
            projects=[_tp(p) for p in page.projects],
            total=page.total,
            returned=len(page.projects),
            offset=page.offset,
            limit=page.limit,
        )

    def list_grants(
        self, repo_id: str, limit: int = 50, offset: int = 0
    ) -> GrantsResponse:
        page: GrantPage = self._service.list_grants_page(repo_id, limit, offset)
        return GrantsResponse(
            repo_id=repo_id,
            grants=[
                GrantResponse(
                    repo_id=g.repo_id, grantee_org_id=g.grantee_org_id, direction=g.direction)
                for g in page.grants
            ],
            total=page.total,
            returned=len(page.grants),
            offset=page.offset,
            limit=page.limit,
        )
