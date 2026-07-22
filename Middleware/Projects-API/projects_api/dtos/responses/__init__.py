"""Outbound response DTOs (never expose raw database documents)."""
from __future__ import annotations

from datetime import datetime

from projects_api.common.models import TypedModel
from projects_api.dtos.common import PageMeta


class ProjectResponse(TypedModel):
    """Public view of a project in the evidence store."""

    project_key: str
    name: str
    category: str | None = None
    issue_count: int = 0
    open_issue_count: int = 0


class ProjectSearchResponse(TypedModel):
    """Paginated project search result."""

    items: list[ProjectResponse]
    page: PageMeta


class ProjectMetricsResponse(TypedModel):
    """Latest computed delivery-health metrics for a project."""

    project_key: str
    computed_at: datetime
    backlog_growth: float
    reopen_rate: float
    blocker_count: int
    dependency_depth: int
    issue_aging_days: float = 0.0
    resolution_velocity: float = 0.0
    resolution_velocity_trend: float = 0.0
    contributor_concentration: float = 0.0
    critical_defect_ratio: float = 0.0


class ProjectMetricsHistoryResponse(TypedModel):
    """Time series of a project's computed metrics (newest first)."""

    project_key: str
    history: list[ProjectMetricsResponse]


class ProjectGroupResponse(TypedModel):
    """A user-defined named group of project keys."""

    group_key: str
    name: str
    description: str = ""
    project_keys: list[str] = []
    created_at: datetime
    updated_at: datetime


class ProjectGroupListResponse(TypedModel):
    """All project groups (newest first)."""

    items: list[ProjectGroupResponse]


class HealthResponse(TypedModel):
    """Liveness / readiness payload."""

    status: str
    service: str
    dependencies: dict[str, str] = {}
