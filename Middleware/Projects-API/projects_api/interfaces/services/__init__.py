"""Abstract service contracts. Concrete implementations live in ``services/``."""
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


class ProjectQueryService(ABC):
    @abstractmethod
    def search(self, request: SearchProjectsRequest) -> ProjectSearchResponse: ...

    @abstractmethod
    def get(self, project_key: str) -> ProjectResponse: ...


class ProjectMetricsService(ABC):
    @abstractmethod
    def latest(self, project_key: str) -> ProjectMetricsResponse: ...

    @abstractmethod
    def history(self, project_key: str, limit: int) -> list[ProjectMetricsResponse]: ...


class ProjectGroupsService(ABC):
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


class MetricsComputationService(ABC):
    @abstractmethod
    def compute(self, project_key: str) -> ProjectMetricsResponse: ...

    @abstractmethod
    def compute_all(self, limit: int) -> list[str]: ...
