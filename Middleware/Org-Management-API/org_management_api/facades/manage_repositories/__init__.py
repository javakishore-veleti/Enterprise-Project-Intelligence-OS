"""Use case: repositories, tracker projects, visibility, and grants."""
from __future__ import annotations

from org_management_api.dtos.common import (
    RepositoryGrantRecord,
    RepositoryRecord,
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

    def list_repositories(self, org_id: str) -> RepositoriesResponse:
        repos = self._service.list_repositories(org_id)
        return RepositoriesResponse(org_id=org_id, repositories=[_repo(r) for r in repos])
