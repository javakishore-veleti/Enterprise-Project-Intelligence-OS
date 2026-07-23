"""Abstract facade contracts. Concrete implementations live in ``facades/``."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from projects_api.dtos.requests import (
    CreateProjectGroupRequest,
    ScopedProjectSearchRequest,
    SearchProjectsRequest,
    UpdateProjectGroupRequest,
)
from projects_api.dtos.common import OrgScope
from projects_api.dtos.responses import (
    ForecastSubjectsResponse,
    PortfolioSummaryResponse,
    ProjectGroupListResponse,
    ProjectGroupResponse,
    ProjectMetricsResponse,
    ProjectResponse,
    ProjectSearchResponse,
    ScopedProjectSearchResponse,
)


class SearchProjectsUseCase(ABC):
    @abstractmethod
    def execute(
        self, request: SearchProjectsRequest, org_scope: OrgScope | None = None
    ) -> ProjectSearchResponse: ...


class SearchProjectsScopedUseCase(ABC):
    @abstractmethod
    def execute(
        self, request: ScopedProjectSearchRequest, org_scope: OrgScope | None = None
    ) -> ScopedProjectSearchResponse: ...


class GetProjectUseCase(ABC):
    @abstractmethod
    def execute(
        self, project_key: str, org_scope: OrgScope | None = None
    ) -> ProjectResponse: ...


class GetProjectMetricsUseCase(ABC):
    @abstractmethod
    def execute(
        self, project_key: str, org_scope: OrgScope | None = None
    ) -> ProjectMetricsResponse: ...


class ForecastSubjectsUseCase(ABC):
    @abstractmethod
    def execute(self, project_key: str) -> ForecastSubjectsResponse: ...


class PortfolioSummaryUseCase(ABC):
    @abstractmethod
    def execute(
        self,
        top: int,
        user_key: str | None = None,
        as_of: date | None = None,
        org_scope: OrgScope | None = None,
    ) -> PortfolioSummaryResponse: ...


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
