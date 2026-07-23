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


class ProjectSearchItem(TypedModel):
    """One project in the scale-hardened, risk-ranked search result.

    ``risk_score``/``risk_band`` are null for projects that have no computed
    metrics yet (ranked last)."""

    project_key: str
    name: str
    risk_score: float | None = None
    risk_band: str | None = None
    open_issue_count: int = 0


class ScopedProjectSearchResponse(TypedModel):
    """Server-side, paginated, risk-ranked project search result.

    ``total`` is the full match count (for the pager); ``returned`` is how many
    items this page carries. Ordered by ``risk_score`` desc (nulls last), then
    ``project_key``. Optionally scoped to a user's assigned projects.

    (Distinct from ``ProjectSearchResponse`` — which backs the pre-existing bare
    ``GET /api/v1/projects`` list — because this endpoint carries risk fields and
    a flat pager shape; kept separate so existing behavior is unchanged.)"""

    total: int
    returned: int
    offset: int
    limit: int
    items: list[ProjectSearchItem]


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


class ForecastSubjectFacet(TypedModel):
    """One selectable forecast subject value with how many issues carry it."""

    value: str
    count: int


class ForecastSubjectsResponse(TypedModel):
    """The available forecast subjects for a project — the release / component /
    tag values a forecast can be scoped to, each with its issue count (desc)."""

    project_key: str
    releases: list[ForecastSubjectFacet] = []
    components: list[ForecastSubjectFacet] = []
    tags: list[ForecastSubjectFacet] = []


class PortfolioTotals(TypedModel):
    """Portfolio-wide roll-up counts."""

    projects: int
    issues: int
    open_issues: int


class PortfolioRiskBands(TypedModel):
    """How the portfolio's projects distribute across risk bands."""

    high: int
    medium: int
    low: int
    unscored: int


class PortfolioProjectSummary(TypedModel):
    """One ranked project in the portfolio summary's top-N list."""

    project_key: str
    name: str
    category: str | None = None
    risk_score: float
    risk_band: str
    issue_count: int = 0
    open_issue_count: int = 0
    blocker_count: int = 0
    reopen_rate: float = 0.0
    issue_aging_days: float = 0.0
    critical_defect_ratio: float = 0.0
    headline: str


class PortfolioScope(TypedModel):
    """Who the portfolio summary was scoped to (per-user scoping seam).

    ``scoped`` is True only when a known ``user_key`` with assignments narrowed
    the ranking to that user's projects; otherwise the summary covers ALL
    projects and ``user_key`` reflects the (possibly absent) caller.
    """

    user_key: str | None = None
    project_count: int = 0
    scoped: bool = False


class PortfolioSummaryResponse(TypedModel):
    """Server-side risk ranking of the portfolio; only the top-N are returned.

    Optionally scoped to a caller's assigned projects (``scope``). ``portfolio_score``
    is a severity-weighted 0..100 roll-up of the scoped projects.

    ``as_of`` echoes the applied point-in-time date (ISO ``YYYY-MM-DD``) when the
    caller asked for a historical view — totals/bands/scores then reflect each
    project's latest metrics snapshot on/before that date; ``null`` means the
    newest snapshot per project (live view).
    """

    scope: PortfolioScope
    as_of: str | None = None
    portfolio_score: float
    overall_risk: str
    totals: PortfolioTotals
    risk_bands: PortfolioRiskBands
    top_projects: list[PortfolioProjectSummary]
    computed_at: str


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
