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


class MetricsComputationDao(ABC):
    """Reads raw evidence + writes computed metrics (MongoDB). Deterministic — no LLM."""

    @abstractmethod
    def list_project_keys(self, limit: int) -> list[str]: ...

    @abstractmethod
    def counts(self, project_key: str) -> dict:
        """{issue_count, open_issue_count, blocker_count, resolved_count}."""

    @abstractmethod
    def reopened_count(self, project_key: str) -> int: ...

    @abstractmethod
    def reference_date(self, project_key: str):
        """Latest issue ``created_at`` for the project (the data-relative 'now'), or None."""

    @abstractmethod
    def created_between(self, project_key: str, start, end) -> int: ...

    @abstractmethod
    def resolved_between(self, project_key: str, start, end) -> int: ...

    @abstractmethod
    def blocking_links(self, project_key: str) -> list[tuple[str, str]]:
        """(source_issue_key, target_issue_key) for blocks/depends links in the project."""

    @abstractmethod
    def avg_open_age_days(self, project_key: str, reference) -> float:
        """Average age (days) of open issues relative to the reference date."""

    @abstractmethod
    def top_contributor_share(self, project_key: str) -> float:
        """Top contributor's share (0-1) of comment/history activity."""

    @abstractmethod
    def critical_open_count(self, project_key: str) -> int:
        """Open issues with Blocker/Critical priority."""

    @abstractmethod
    def write_metrics(self, project_key: str, metrics: dict, computed_at) -> None: ...

    @abstractmethod
    def update_project_counts(self, project_key: str, issue_count: int, open_issue_count: int) -> None: ...
