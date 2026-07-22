"""Risk analysis endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi import Query

from risk_analytics_api.api.dependencies import (
    provide_get_analysis_run_facade,
    provide_get_attention_feed_facade,
    provide_get_dashboard_activity_facade,
    provide_list_analysis_runs_facade,
    provide_start_portfolio_analysis_facade,
    provide_start_project_analysis_facade,
)
from risk_analytics_api.dtos.requests import StartAnalysisRequest, StartPortfolioAnalysisRequest
from risk_analytics_api.dtos.responses import (
    AnalysisRunListResponse,
    AnalysisRunResponse,
    AttentionResponse,
    DashboardActivityResponse,
)
from risk_analytics_api.facades.get_analysis_run import GetAnalysisRunFacade
from risk_analytics_api.facades.get_attention_feed import GetAttentionFeedFacade
from risk_analytics_api.facades.get_dashboard_activity import GetDashboardActivityFacade
from risk_analytics_api.facades.list_analysis_runs import ListAnalysisRunsFacade
from risk_analytics_api.facades.start_portfolio_analysis import StartPortfolioAnalysisFacade
from risk_analytics_api.facades.start_project_analysis import StartProjectAnalysisFacade

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.get("/activity", response_model=DashboardActivityResponse,
            operation_id="getDashboardActivity")
def get_dashboard_activity(
    limit: int = Query(default=15, ge=1, le=100),
    facade: GetDashboardActivityFacade = Depends(provide_get_dashboard_activity_facade),
) -> DashboardActivityResponse:
    return facade.execute(limit)


@router.get("/attention", response_model=AttentionResponse, operation_id="getAttentionFeed")
def get_attention_feed(
    top: int = Query(default=10, ge=1, le=100),
    as_of: str | None = Query(
        default=None,
        description="ISO date (YYYY-MM-DD). Include only findings on or before the end of that day.",
    ),
    projects: str | None = Query(
        default=None,
        description="Comma-separated project_keys to scope to. Absent -> all projects.",
    ),
    offset: int = Query(default=0, ge=0),
    facade: GetAttentionFeedFacade = Depends(provide_get_attention_feed_facade),
) -> AttentionResponse:
    parsed_as_of: date | None = None
    if as_of is not None:
        try:
            parsed_as_of = date.fromisoformat(as_of)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="as_of must be an ISO date (YYYY-MM-DD)",
            )
    project_list: list[str] | None = None
    if projects:
        project_list = [p.strip() for p in projects.split(",") if p.strip()]
        if not project_list:
            project_list = None
    return facade.execute(top, parsed_as_of, project_list, offset)


@router.get("/projects/{project_key}/runs", response_model=AnalysisRunListResponse,
            operation_id="listProjectAnalysisRuns")
def list_project_runs(
    project_key: str,
    limit: int = Query(default=20, ge=1, le=100),
    facade: ListAnalysisRunsFacade = Depends(provide_list_analysis_runs_facade),
) -> AnalysisRunListResponse:
    return facade.execute(project_key, limit)


@router.post(
    "/projects/{project_key}",
    response_model=AnalysisRunResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="startProjectAnalysis",
)
def start_project_analysis(
    project_key: str,
    request: StartAnalysisRequest,
    facade: StartProjectAnalysisFacade = Depends(provide_start_project_analysis_facade),
) -> AnalysisRunResponse:
    return facade.execute(project_key, request)


@router.post(
    "/portfolios/{portfolio_key}",
    response_model=AnalysisRunResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="startPortfolioAnalysis",
)
def start_portfolio_analysis(
    portfolio_key: str,
    request: StartPortfolioAnalysisRequest,
    facade: StartPortfolioAnalysisFacade = Depends(provide_start_portfolio_analysis_facade),
) -> AnalysisRunResponse:
    return facade.execute(portfolio_key, request)


@router.get(
    "/runs/{run_id}",
    response_model=AnalysisRunResponse,
    operation_id="getAnalysisRun",
)
def get_analysis_run(
    run_id: str,
    facade: GetAnalysisRunFacade = Depends(provide_get_analysis_run_facade),
) -> AnalysisRunResponse:
    return facade.execute(run_id)
