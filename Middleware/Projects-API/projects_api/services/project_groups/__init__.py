"""Project-groups service — CRUD business rules over the groups DAO.

Owns slug generation, conflict detection, not-found handling, and timestamp
bookkeeping. Deterministic; no LLM, no direct DB access.
"""
from __future__ import annotations

from projects_api.common.exceptions import ConflictError, NotFoundError, ValidationError
from projects_api.common.utilities import slugify, utc_now
from projects_api.dtos.requests import (
    CreateProjectGroupRequest,
    UpdateProjectGroupRequest,
)
from projects_api.dtos.responses import ProjectGroupListResponse, ProjectGroupResponse
from projects_api.interfaces.daos import ProjectGroupsDao
from projects_api.interfaces.services import ProjectGroupsService


class DefaultProjectGroupsService(ProjectGroupsService):
    def __init__(self, groups_dao: ProjectGroupsDao) -> None:
        self._dao = groups_dao

    def list_groups(self) -> ProjectGroupListResponse:
        return ProjectGroupListResponse(items=self._dao.list_all())

    def get_group(self, group_key: str) -> ProjectGroupResponse:
        group = self._dao.get(group_key)
        if group is None:
            raise NotFoundError(f"project group '{group_key}' not found")
        return group

    def create_group(self, request: CreateProjectGroupRequest) -> ProjectGroupResponse:
        group_key = slugify(request.name)
        if not group_key:
            raise ValidationError("name must contain at least one alphanumeric character")
        if self._dao.get(group_key) is not None:
            raise ConflictError(f"project group '{group_key}' already exists")
        now = utc_now()
        record = ProjectGroupResponse(
            group_key=group_key,
            name=request.name,
            description=request.description,
            project_keys=list(request.project_keys),
            created_at=now,
            updated_at=now,
        )
        return self._dao.insert(record)

    def update_group(
        self, group_key: str, request: UpdateProjectGroupRequest
    ) -> ProjectGroupResponse:
        existing = self.get_group(group_key)
        updated = existing.model_copy(update={
            "name": existing.name if request.name is None else request.name,
            "description": (
                existing.description if request.description is None else request.description
            ),
            "project_keys": (
                existing.project_keys
                if request.project_keys is None
                else list(request.project_keys)
            ),
            "updated_at": utc_now(),
        })
        return self._dao.replace(updated)

    def delete_group(self, group_key: str) -> None:
        if not self._dao.delete(group_key):
            raise NotFoundError(f"project group '{group_key}' not found")
