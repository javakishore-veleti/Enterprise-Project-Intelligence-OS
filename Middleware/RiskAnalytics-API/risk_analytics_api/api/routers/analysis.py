"""Risk analysis endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi import Query

from risk_analytics_api.api.dependencies import (
    provide_approve_decision_facade,
    provide_get_analysis_run_facade,
    provide_get_attention_feed_facade,
    provide_get_dashboard_activity_facade,
    provide_get_decision_facade,
    provide_get_early_warnings_facade,
    provide_get_forecast_facade,
    provide_get_investigation_facade,
    provide_get_scenario_facade,
    provide_investigate_project_facade,
    provide_list_analysis_runs_facade,
    provide_list_decisions_facade,
    provide_list_forecasts_facade,
    provide_list_investigation_templates_facade,
    provide_list_investigations_facade,
    provide_list_scenarios_facade,
    provide_run_decision_facade,
    provide_run_forecast_facade,
    provide_run_scenario_facade,
    provide_select_option_facade,
    provide_start_portfolio_analysis_facade,
    provide_start_project_analysis_facade,
)
from risk_analytics_api.dtos.requests import (
    DecisionRequest,
    ForecastRequest,
    InvestigateRequest,
    ScenarioRequest,
    SelectOptionRequest,
    StartAnalysisRequest,
    StartPortfolioAnalysisRequest,
)
from risk_analytics_api.dtos.responses import (
    AnalysisRunListResponse,
    AnalysisRunResponse,
    AttentionResponse,
    DashboardActivityResponse,
    DecisionResponse,
    DecisionsPageResponse,
    EarlyWarningsResponse,
    ForecastResponse,
    ForecastsPageResponse,
    InvestigationResponse,
    InvestigationsPageResponse,
    InvestigationTemplateResponse,
    ScenarioResponse,
    ScenariosPageResponse,
)
from risk_analytics_api.facades.approve_decision import ApproveDecisionFacade
from risk_analytics_api.facades.get_analysis_run import GetAnalysisRunFacade
from risk_analytics_api.facades.get_attention_feed import GetAttentionFeedFacade
from risk_analytics_api.facades.get_dashboard_activity import GetDashboardActivityFacade
from risk_analytics_api.facades.get_decision import GetDecisionFacade
from risk_analytics_api.facades.get_early_warnings import GetEarlyWarningsFacade
from risk_analytics_api.facades.get_forecast import GetForecastFacade
from risk_analytics_api.facades.get_investigation import GetInvestigationFacade
from risk_analytics_api.facades.get_scenario import GetScenarioFacade
from risk_analytics_api.facades.investigate_project import InvestigateProjectFacade
from risk_analytics_api.facades.list_analysis_runs import ListAnalysisRunsFacade
from risk_analytics_api.facades.list_decisions import ListDecisionsFacade
from risk_analytics_api.facades.list_forecasts import ListForecastsFacade
from risk_analytics_api.facades.list_investigation_templates import (
    ListInvestigationTemplatesFacade,
)
from risk_analytics_api.facades.list_investigations import ListInvestigationsFacade
from risk_analytics_api.facades.list_scenarios import ListScenariosFacade
from risk_analytics_api.facades.run_decision import RunDecisionFacade
from risk_analytics_api.facades.run_forecast import RunForecastFacade
from risk_analytics_api.facades.run_scenario import RunScenarioFacade
from risk_analytics_api.facades.select_option import SelectOptionFacade
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
    "/investigate",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="investigateProject",
)
def investigate_project(
    request: InvestigateRequest,
    facade: InvestigateProjectFacade = Depends(provide_investigate_project_facade),
) -> InvestigationResponse:
    return facade.execute(request)


@router.get(
    "/investigations",
    response_model=InvestigationsPageResponse,
    operation_id="listInvestigations",
)
def list_investigations(
    scope: str | None = Query(
        default=None, description="Filter to investigations requested_by this subject."),
    q: str | None = Query(
        default=None,
        description="Case-insensitive search across project_key, question, and root_cause.",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    facade: ListInvestigationsFacade = Depends(provide_list_investigations_facade),
) -> InvestigationsPageResponse:
    return facade.execute(scope, q, limit, offset)


@router.get(
    "/investigation-templates",
    response_model=list[InvestigationTemplateResponse],
    operation_id="listInvestigationTemplates",
)
def list_investigation_templates(
    facade: ListInvestigationTemplatesFacade = Depends(
        provide_list_investigation_templates_facade),
) -> list[InvestigationTemplateResponse]:
    return facade.execute()


@router.get(
    "/investigations/{investigation_id}",
    response_model=InvestigationResponse,
    operation_id="getInvestigation",
)
def get_investigation(
    investigation_id: str,
    facade: GetInvestigationFacade = Depends(provide_get_investigation_facade),
) -> InvestigationResponse:
    return facade.execute(investigation_id)


# --- Predict: Delivery Forecast -------------------------------------------


@router.post(
    "/forecast",
    response_model=ForecastResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="runForecast",
)
def run_forecast(
    request: ForecastRequest,
    facade: RunForecastFacade = Depends(provide_run_forecast_facade),
) -> ForecastResponse:
    return facade.execute(request)


@router.get(
    "/forecasts",
    response_model=ForecastsPageResponse,
    operation_id="listForecasts",
)
def list_forecasts(
    scope: str | None = Query(
        default=None, description="Filter to forecasts requested_by this subject."),
    q: str | None = Query(
        default=None,
        description="Case-insensitive search across project_key and narrative.",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    facade: ListForecastsFacade = Depends(provide_list_forecasts_facade),
) -> ForecastsPageResponse:
    return facade.execute(scope, q, limit, offset)


@router.get(
    "/forecasts/{forecast_id}",
    response_model=ForecastResponse,
    operation_id="getForecast",
)
def get_forecast(
    forecast_id: str,
    facade: GetForecastFacade = Depends(provide_get_forecast_facade),
) -> ForecastResponse:
    return facade.execute(forecast_id)


# --- Predict: Digital-Twin Scenario Simulator -----------------------------


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="runScenario",
)
def run_scenario(
    request: ScenarioRequest,
    facade: RunScenarioFacade = Depends(provide_run_scenario_facade),
) -> ScenarioResponse:
    return facade.execute(request)


@router.get(
    "/scenarios",
    response_model=ScenariosPageResponse,
    operation_id="listScenarios",
)
def list_scenarios(
    scope: str | None = Query(
        default=None, description="Filter to scenarios requested_by this subject."),
    q: str | None = Query(
        default=None,
        description="Case-insensitive search across project_key, scenario, and narrative.",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    facade: ListScenariosFacade = Depends(provide_list_scenarios_facade),
) -> ScenariosPageResponse:
    return facade.execute(scope, q, limit, offset)


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
    operation_id="getScenario",
)
def get_scenario(
    scenario_id: str,
    facade: GetScenarioFacade = Depends(provide_get_scenario_facade),
) -> ScenarioResponse:
    return facade.execute(scenario_id)


# --- Decide: Options-first decision support --------------------------------


@router.post(
    "/decide",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="runDecision",
)
def run_decision(
    request: DecisionRequest,
    facade: RunDecisionFacade = Depends(provide_run_decision_facade),
) -> DecisionResponse:
    return facade.execute(request)


@router.get(
    "/decisions",
    response_model=DecisionsPageResponse,
    operation_id="listDecisions",
)
def list_decisions(
    scope: str | None = Query(
        default=None, description="Filter to decisions requested_by this subject."),
    q: str | None = Query(
        default=None,
        description="Case-insensitive search across project_key and narrative.",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    facade: ListDecisionsFacade = Depends(provide_list_decisions_facade),
) -> DecisionsPageResponse:
    return facade.execute(scope, q, limit, offset)


@router.get(
    "/decisions/{decision_id}",
    response_model=DecisionResponse,
    operation_id="getDecision",
)
def get_decision(
    decision_id: str,
    facade: GetDecisionFacade = Depends(provide_get_decision_facade),
) -> DecisionResponse:
    return facade.execute(decision_id)


@router.post(
    "/decisions/{decision_id}/select",
    response_model=DecisionResponse,
    operation_id="selectDecisionOption",
)
def select_decision_option(
    decision_id: str,
    request: SelectOptionRequest,
    facade: SelectOptionFacade = Depends(provide_select_option_facade),
) -> DecisionResponse:
    return facade.execute(decision_id, request)


@router.post(
    "/decisions/{decision_id}/approve",
    response_model=DecisionResponse,
    operation_id="approveDecision",
)
def approve_decision(
    decision_id: str,
    facade: ApproveDecisionFacade = Depends(provide_approve_decision_facade),
) -> DecisionResponse:
    return facade.execute(decision_id)


# --- Predict: Early-Warning (computed on read) ----------------------------


@router.get(
    "/early-warnings",
    response_model=EarlyWarningsResponse,
    operation_id="getEarlyWarnings",
)
def get_early_warnings(
    scope: str | None = Query(
        default=None,
        description="Comma-separated project_keys to scope to. Absent -> all projects.",
    ),
    limit: int = Query(default=10, ge=1, le=100),
    facade: GetEarlyWarningsFacade = Depends(provide_get_early_warnings_facade),
) -> EarlyWarningsResponse:
    return facade.execute(scope, limit)


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
