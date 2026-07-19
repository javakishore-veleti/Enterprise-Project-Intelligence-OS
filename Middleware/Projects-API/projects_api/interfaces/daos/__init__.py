"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from projects_api.dtos.responses import ProjectMetricsResponse, ProjectResponse


class ProjectsDao(ABC):
    """Read access to the project evidence collection (MongoDB)."""

    @abstractmethod
    def search(self, query: str | None, limit: int, offset: int) -> tuple[list[ProjectResponse], int]:
        """Return (page of projects, total match count)."""

    @abstractmethod
    def get(self, project_key: str) -> ProjectResponse | None: ...


class ProjectMetricsDao(ABC):
    """Read access to computed project metrics (MongoDB)."""

    @abstractmethod
    def latest(self, project_key: str) -> ProjectMetricsResponse | None: ...
