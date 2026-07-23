"""Repository / tracker-project / visibility / grant endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from org_management_api.api.dependencies import provide_manage_repositories_facade
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
def list_repositories(org_id: str, facade: ManageRepositoriesFacade = Facade):
    return facade.list_repositories(org_id)


@router.post("/repositories/{repo_id}/projects", response_model=TrackerProjectsResponse,
             status_code=status.HTTP_201_CREATED, operation_id="addTrackerProjects")
def add_tracker_projects(
    repo_id: str, request: AddTrackerProjectsRequest, facade: ManageRepositoriesFacade = Facade
):
    return facade.add_tracker_projects(repo_id, request)


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
