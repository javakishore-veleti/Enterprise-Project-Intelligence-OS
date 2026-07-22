"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from projects_api.dtos.common import PortfolioAggregate
from projects_api.dtos.responses import (
    ProjectGroupResponse,
    ProjectMetricsResponse,
    ProjectResponse,
)


class ProjectsDao(ABC):
    """Read access to the project evidence collection (MongoDB)."""

    @abstractmethod
    def search(self, query: str | None, limit: int, offset: int) -> tuple[list[ProjectResponse], int]:
        """Return (page of projects, total match count)."""

    @abstractmethod
    def get(self, project_key: str) -> ProjectResponse | None: ...


class ProjectGroupsDao(ABC):
    """Read/write access to user-defined project groups (MongoDB)."""

    @abstractmethod
    def list_all(self) -> list[ProjectGroupResponse]:
        """Every group, newest first (by ``created_at``)."""

    @abstractmethod
    def get(self, group_key: str) -> ProjectGroupResponse | None: ...

    @abstractmethod
    def insert(self, record: ProjectGroupResponse) -> ProjectGroupResponse:
        """Persist a new group record and return it."""

    @abstractmethod
    def replace(self, record: ProjectGroupResponse) -> ProjectGroupResponse:
        """Replace an existing group (matched by ``group_key``) and return it."""

    @abstractmethod
    def delete(self, group_key: str) -> bool:
        """Delete a group; return True if a document was removed."""


class ProjectMetricsDao(ABC):
    """Read access to computed project metrics (MongoDB)."""

    @abstractmethod
    def latest(self, project_key: str) -> ProjectMetricsResponse | None: ...

    @abstractmethod
    def history(self, project_key: str, limit: int) -> list[ProjectMetricsResponse]:
        """Past metric snapshots for a project (newest first) — the time series."""


class PortfolioSummaryDao(ABC):
    """Read access for the portfolio risk ranking (MongoDB). Joins projects with
    their latest metrics and rolls up totals server-side."""

    @abstractmethod
    def portfolio_data(
        self,
        project_keys: list[str] | None = None,
        as_of: date | None = None,
    ) -> PortfolioAggregate:
        """Totals over projects + latest-metrics rows for scored projects.

        When ``project_keys`` is provided, the aggregation is narrowed to those
        keys **in the database** (``$match project_key $in [...]``) so scoping
        never pulls the full portfolio into Python.

        When ``as_of`` is provided, each project's scored row is drawn from its
        latest metrics snapshot with ``computed_at <= end-of-day(as_of)`` (the
        ``$match`` on ``computed_at`` runs **in the database** before the
        latest-per-project group); projects with no qualifying snapshot drop out
        and are counted as unscored.
        """


class ProjectAssignmentsDao(ABC):
    """Read access to per-user project assignments (MongoDB). The scoping seam:
    resolves a caller's ``user_key`` to the project keys they own/manage/belong to."""

    @abstractmethod
    def project_keys_for(self, user_key: str) -> list[str]:
        """Project keys assigned to ``user_key`` (indexed lookup); [] if none."""


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
