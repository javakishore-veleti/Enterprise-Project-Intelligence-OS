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


class OrgScope(TypedModel):
    """The authoritative project-key set a caller may see, resolved from the
    Org-Management-API (Phase-2 multi-tenancy).

    Semantics (deliberate): an ``OrgScope`` object being *present* means org
    scoping applies — the allowed keys become an authoritative ``$in`` on every
    project-scoped read, AND-composed with any existing (``X-User-Key`` /
    ``scope``) narrowing. An *empty* ``project_keys`` therefore means the caller
    sees nothing (correct isolation), NOT everything. The absence of an
    ``OrgScope`` (``None``) means no org headers were supplied (or the org API
    was unreachable) — the legacy scope path is left 100% unchanged.
    """

    project_keys: tuple[str, ...] = ()

    def as_list(self) -> list[str]:
        return list(self.project_keys)

    def allows(self, project_key: str) -> bool:
        return project_key in self.project_keys


class ProjectSearchScoredRow(TypedModel):
    """DAO->service carrier for the scoped project search: one matched project
    joined with its latest metrics snapshot. ``has_metrics`` is False when the
    project has no metrics doc yet — the service then ranks it unscored
    (``risk_score``/``risk_band`` null, sorted last). The metric fields feed the
    same composite ``risk_score`` the portfolio ranking uses (reused, not
    recomputed differently)."""

    project_key: str
    name: str
    open_issue_count: int = 0
    issue_count: int = 0
    has_metrics: bool = False
    blocker_count: int = 0
    reopen_rate: float = 0.0
    issue_aging_days: float = 0.0
    critical_defect_ratio: float = 0.0
