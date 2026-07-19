"""Abstract facade contracts. Concrete implementations live in ``facades/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from projects_api.dtos.requests import SearchProjectsRequest
from projects_api.dtos.responses import (
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
