"""Repository / tracker-project / visibility / grant endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from org_management_api.api.dependencies import provide_manage_repositories_facade
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
    TrackerProjectsResponse,
)
from org_management_api.facades.manage_repositories import ManageRepositoriesFacade

router = APIRouter(prefix="/api/v1", tags=["repositories"])

Facade = Depends(provide_manage_repositories_facade)


@router.post("/orgs/{org_id}/repositories", response_model=RepositoryResponse,
             status_code=status.HTTP_201_CREATED, operation_id="createRepository")
def create_repository(
    org_id: str, request: CreateRepositoryRequest, facade: ManageRepositoriesFacade = Facade
):
    return facade.create_repository(org_id, request)


@router.get("/orgs/{org_id}/repositories", response_model=RepositoriesResponse,
            operation_id="listOrganizationRepositories")
def list_repositories(
    org_id: str,
    q: str | None = Query(
        default=None, description="Substring filter on provider / external_account."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: ManageRepositoriesFacade = Facade,
):
    # Server-paged + filterable so an org with many connected repos stays bounded.
    return facade.list_repositories(org_id, q, limit, offset)


@router.post("/repositories/{repo_id}/projects", response_model=TrackerProjectsResponse,
             status_code=status.HTTP_201_CREATED, operation_id="addTrackerProjects")
def add_tracker_projects(
    repo_id: str, request: AddTrackerProjectsRequest, facade: ManageRepositoriesFacade = Facade
):
    return facade.add_tracker_projects(repo_id, request)


@router.get("/repositories/{repo_id}/projects", response_model=TrackerProjectsResponse,
            operation_id="listRepositoryProjects")
def list_repository_projects(
    repo_id: str,
    q: str | None = Query(
        default=None, description="Substring filter on external_key / name."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: ManageRepositoriesFacade = Facade,
):
    # A repo can carry thousands of tracker projects — paged + searchable.
    return facade.list_tracker_projects(repo_id, q, limit, offset)


@router.get("/repositories/{repo_id}/grants", response_model=GrantsResponse,
            operation_id="listRepositoryGrants")
def list_repository_grants(
    repo_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: ManageRepositoriesFacade = Facade,
):
    return facade.list_grants(repo_id, limit, offset)


@router.put("/repositories/{repo_id}/visibility", response_model=RepositoryResponse,
            operation_id="updateRepositoryVisibility")
def update_visibility(
    repo_id: str, request: UpdateVisibilityRequest, facade: ManageRepositoriesFacade = Facade
):
    return facade.set_visibility(repo_id, request)


@router.post("/repositories/{repo_id}/grants", response_model=GrantResponse,
             status_code=status.HTTP_201_CREATED, operation_id="addRepositoryGrant")
def add_grant(
    repo_id: str, request: AddGrantRequest, facade: ManageRepositoriesFacade = Facade
):
    return facade.add_grant(repo_id, request)
