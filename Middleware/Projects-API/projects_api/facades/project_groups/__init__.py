"""Use case: CRUD over user-defined project groups."""
from __future__ import annotations

from projects_api.dtos.requests import (
    CreateProjectGroupRequest,
    UpdateProjectGroupRequest,
)
from projects_api.dtos.responses import ProjectGroupListResponse, ProjectGroupResponse
from projects_api.interfaces.facades import ProjectGroupsUseCase
from projects_api.interfaces.services import ProjectGroupsService


class ProjectGroupsFacade(ProjectGroupsUseCase):
    def __init__(self, service: ProjectGroupsService) -> None:
        self._service = service

    def list_groups(self) -> ProjectGroupListResponse:
        return self._service.list_groups()

    def get_group(self, group_key: str) -> ProjectGroupResponse:
        return self._service.get_group(group_key)

    def create_group(self, request: CreateProjectGroupRequest) -> ProjectGroupResponse:
        return self._service.create_group(request)

    def update_group(
        self, group_key: str, request: UpdateProjectGroupRequest
    ) -> ProjectGroupResponse:
        return self._service.update_group(group_key, request)

    def delete_group(self, group_key: str) -> None:
        self._service.delete_group(group_key)
