"""Risk analysis endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from risk_analytics_api.api.dependencies import (
    provide_get_analysis_run_facade,
    provide_start_portfolio_analysis_facade,
    provide_start_project_analysis_facade,
)
from risk_analytics_api.dtos.requests import StartAnalysisRequest, StartPortfolioAnalysisRequest
from risk_analytics_api.dtos.responses import AnalysisRunResponse
from risk_analytics_api.facades.get_analysis_run import GetAnalysisRunFacade
from risk_analytics_api.facades.start_portfolio_analysis import StartPortfolioAnalysisFacade
from risk_analytics_api.facades.start_project_analysis import StartProjectAnalysisFacade

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


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
