"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from projects_api.dtos.requests import SearchProjectsRequest
from projects_api.dtos.responses import (
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
