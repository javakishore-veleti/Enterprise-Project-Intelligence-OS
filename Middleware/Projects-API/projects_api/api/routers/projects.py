"""Project query endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Header, Query

from projects_api.api.dependencies import (
    provide_compute_metrics_facade,
    provide_forecast_subjects_facade,
    provide_get_project_facade,
    provide_get_project_metrics_facade,
    provide_org_scope,
    provide_portfolio_summary_facade,
    provide_search_projects_facade,
    provide_search_projects_scoped_facade,
)
from projects_api.dtos.common import OrgScope
from projects_api.dtos.requests import ScopedProjectSearchRequest, SearchProjectsRequest
from projects_api.dtos.responses import (
    ForecastSubjectsResponse,
    PortfolioSummaryResponse,
    ProjectMetricsHistoryResponse,
    ProjectMetricsResponse,
    ProjectResponse,
    ProjectSearchResponse,
    ScopedProjectSearchResponse,
)
from projects_api.facades.compute_metrics import ComputeMetricsFacade
from projects_api.facades.forecast_subjects import ForecastSubjectsFacade
from projects_api.facades.get_project import GetProjectFacade
from projects_api.facades.get_project_metrics import GetProjectMetricsFacade
from projects_api.facades.portfolio_summary import PortfolioSummaryFacade
from projects_api.facades.search_projects import SearchProjectsFacade
from projects_api.facades.search_projects_scoped import SearchProjectsScopedFacade

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("/metrics/compute-all", operation_id="computeAllProjectMetrics")
def compute_all_metrics(
    limit: int = Query(default=1000, ge=1, le=5000),
    facade: ComputeMetricsFacade = Depends(provide_compute_metrics_facade),
) -> dict:
    """Recompute metrics for every project from ingested evidence (batch)."""
    computed = facade.compute_all(limit)
    return {"computed": computed, "count": len(computed)}


@router.post("/{project_key}/metrics/compute", response_model=ProjectMetricsResponse,
             operation_id="computeProjectMetrics")
def compute_project_metrics(
    project_key: str,
    facade: ComputeMetricsFacade = Depends(provide_compute_metrics_facade),
) -> ProjectMetricsResponse:
    """Recompute a single project's metrics from ingested evidence."""
    return facade.compute(project_key)


@router.get("", response_model=ProjectSearchResponse, operation_id="searchProjects")
def search_projects(
    query: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    org_scope: OrgScope | None = Depends(provide_org_scope),
    facade: SearchProjectsFacade = Depends(provide_search_projects_facade),
) -> ProjectSearchResponse:
    return facade.execute(
        SearchProjectsRequest(query=query, limit=limit, offset=offset), org_scope
    )


# NOTE: must be declared BEFORE "/{project_key}" so the literal path is not
# captured as a project key by the parameterized route.
@router.get(
    "/search",
    response_model=ScopedProjectSearchResponse,
    operation_id="searchProjectsScoped",
)
def search_projects_scoped(
    scope: str | None = Query(
        default=None,
        description="User key to scope the search to their assigned projects. "
        "Absent -> all projects.",
    ),
    q: str | None = Query(
        default=None,
        description="Case-insensitive substring match on project_key OR name.",
    ),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    org_scope: OrgScope | None = Depends(provide_org_scope),
    facade: SearchProjectsScopedFacade = Depends(provide_search_projects_scoped_facade),
) -> ScopedProjectSearchResponse:
    """Server-side, risk-ranked, paginated project search (scales to thousands
    of projects per user). Ordered by risk_score desc (nulls last), then key.

    Honors the Phase-2 org scope (``X-Org-Subject`` / ``X-Org-Key`` headers)
    AND-composed with the legacy ``scope`` per-user narrowing."""
    return facade.execute(
        ScopedProjectSearchRequest(scope=scope, query=q, limit=limit, offset=offset),
        org_scope,
    )


# NOTE: must be declared BEFORE "/{project_key}" so the literal path is not
# captured as a project key by the parameterized route.
@router.get(
    "/portfolio-summary",
    response_model=PortfolioSummaryResponse,
    operation_id="getPortfolioSummary",
)
def portfolio_summary(
    top: int = Query(default=15, ge=1, le=50),
    as_of: date | None = Query(
        default=None,
        description="Point-in-time view: ISO date YYYY-MM-DD. Totals/bands/scores "
        "reflect each project's latest metrics snapshot on/before this date. "
        "Omit for the live (newest) view.",
    ),
    x_user_key: str | None = Header(default=None, alias="X-User-Key"),
    org_scope: OrgScope | None = Depends(provide_org_scope),
    facade: PortfolioSummaryFacade = Depends(provide_portfolio_summary_facade),
) -> PortfolioSummaryResponse:
    """Server-side risk ranking of the portfolio; returns only the top N.

    When an ``X-User-Key`` header identifies a user with project assignments, the
    ranking + totals + bands are scoped to that user's projects (the per-user
    scoping seam); otherwise it covers the whole portfolio.

    An optional ``as_of`` date yields a historical view: each project's scored
    row is drawn from its latest metrics snapshot on/before that date (both the
    as-of filter and the per-user scoping apply together). A malformed date is
    rejected with 422.
    """
    return facade.execute(top, user_key=x_user_key, as_of=as_of, org_scope=org_scope)


@router.get("/{project_key}", response_model=ProjectResponse, operation_id="getProject")
def get_project(
    project_key: str,
    org_scope: OrgScope | None = Depends(provide_org_scope),
    facade: GetProjectFacade = Depends(provide_get_project_facade),
) -> ProjectResponse:
    return facade.execute(project_key, org_scope)


@router.get(
    "/{project_key}/metrics",
    response_model=ProjectMetricsResponse,
    operation_id="getProjectMetrics",
)
def get_project_metrics(
    project_key: str,
    org_scope: OrgScope | None = Depends(provide_org_scope),
    facade: GetProjectMetricsFacade = Depends(provide_get_project_metrics_facade),
) -> ProjectMetricsResponse:
    return facade.execute(project_key, org_scope)


@router.get(
    "/{project_key}/forecast-subjects",
    response_model=ForecastSubjectsResponse,
    operation_id="getProjectForecastSubjects",
)
def get_forecast_subjects(
    project_key: str,
    facade: ForecastSubjectsFacade = Depends(provide_forecast_subjects_facade),
) -> ForecastSubjectsResponse:
    """Release / component / tag values available as forecast subjects for a project."""
    return facade.execute(project_key)


@router.get(
    "/{project_key}/metrics/history",
    response_model=ProjectMetricsHistoryResponse,
    operation_id="getProjectMetricsHistory",
)
def get_project_metrics_history(
    project_key: str,
    limit: int = Query(default=50, ge=1, le=500),
    org_scope: OrgScope | None = Depends(provide_org_scope),
    facade: GetProjectMetricsFacade = Depends(provide_get_project_metrics_facade),
) -> ProjectMetricsHistoryResponse:
    return ProjectMetricsHistoryResponse(
        project_key=project_key, history=facade.history(project_key, limit, org_scope))
