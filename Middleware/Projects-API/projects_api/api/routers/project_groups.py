"""Project-groups CRUD endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from projects_api.api.dependencies import provide_project_groups_facade
from projects_api.dtos.requests import (
    CreateProjectGroupRequest,
    UpdateProjectGroupRequest,
)
from projects_api.dtos.responses import ProjectGroupListResponse, ProjectGroupResponse
from projects_api.facades.project_groups import ProjectGroupsFacade

router = APIRouter(prefix="/api/v1/project-groups", tags=["project-groups"])


@router.get("", response_model=ProjectGroupListResponse, operation_id="listProjectGroups")
def list_project_groups(
    facade: ProjectGroupsFacade = Depends(provide_project_groups_facade),
) -> ProjectGroupListResponse:
    return facade.list_groups()


@router.post(
    "",
    response_model=ProjectGroupResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createProjectGroup",
)
def create_project_group(
    request: CreateProjectGroupRequest,
    facade: ProjectGroupsFacade = Depends(provide_project_groups_facade),
) -> ProjectGroupResponse:
    return facade.create_group(request)


@router.get(
    "/{group_key}", response_model=ProjectGroupResponse, operation_id="getProjectGroup"
)
def get_project_group(
    group_key: str,
    facade: ProjectGroupsFacade = Depends(provide_project_groups_facade),
) -> ProjectGroupResponse:
    return facade.get_group(group_key)


@router.put(
    "/{group_key}", response_model=ProjectGroupResponse, operation_id="updateProjectGroup"
)
def update_project_group(
    group_key: str,
    request: UpdateProjectGroupRequest,
    facade: ProjectGroupsFacade = Depends(provide_project_groups_facade),
) -> ProjectGroupResponse:
    return facade.update_group(group_key, request)


@router.delete(
    "/{group_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteProjectGroup",
)
def delete_project_group(
    group_key: str,
    facade: ProjectGroupsFacade = Depends(provide_project_groups_facade),
) -> Response:
    facade.delete_group(group_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
