"""Common DTO fragments shared across responses."""
from __future__ import annotations

from projects_api.common.models import TypedModel


class PageMeta(TypedModel):
    """Standard pagination metadata returned with list responses."""

    total: int
    limit: int
    offset: int


class PortfolioScoredRow(TypedModel):
    """One project joined with its latest metrics — the DAO->service carrier for
    portfolio ranking. Only the fields the scoring formula + headline need."""

    project_key: str
    name: str
    category: str | None = None
    issue_count: int = 0
    open_issue_count: int = 0
    blocker_count: int = 0
    reopen_rate: float = 0.0
    issue_aging_days: float = 0.0
    critical_defect_ratio: float = 0.0


class PortfolioAggregate(TypedModel):
    """DAO->service carrier for the whole portfolio: totals over every project
    plus the per-project scored rows (only projects that have a metrics doc)."""

    total_projects: int
    total_issues: int
    total_open_issues: int
    scored: list[PortfolioScoredRow]
