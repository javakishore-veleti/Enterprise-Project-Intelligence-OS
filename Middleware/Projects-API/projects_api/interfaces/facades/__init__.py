"""Abstract facade contracts. Concrete implementations live in ``facades/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from projects_api.dtos.requests import (
    CreateProjectGroupRequest,
    SearchProjectsRequest,
    UpdateProjectGroupRequest,
)
from projects_api.dtos.responses import (
    ProjectGroupListResponse,
    ProjectGroupResponse,
    ProjectMetricsResponse,
    ProjectResponse,
    ProjectSearchResponse,
)


class SearchProjectsUseCase(ABC):
    @abstractmethod
    def execute(self, request: SearchProjectsRequest) -> ProjectSearchResponse: ...


class GetProjectUseCase(ABC):
    @abstractmethod
    def execute(self, project_key: str) -> ProjectResponse: ...


class GetProjectMetricsUseCase(ABC):
    @abstractmethod
    def execute(self, project_key: str) -> ProjectMetricsResponse: ...


class ProjectGroupsUseCase(ABC):
    """CRUD use case for user-defined project groups."""

    @abstractmethod
    def list_groups(self) -> ProjectGroupListResponse: ...

    @abstractmethod
    def get_group(self, group_key: str) -> ProjectGroupResponse: ...

    @abstractmethod
    def create_group(self, request: CreateProjectGroupRequest) -> ProjectGroupResponse: ...

    @abstractmethod
    def update_group(
        self, group_key: str, request: UpdateProjectGroupRequest
    ) -> ProjectGroupResponse: ...

    @abstractmethod
    def delete_group(self, group_key: str) -> None: ...
