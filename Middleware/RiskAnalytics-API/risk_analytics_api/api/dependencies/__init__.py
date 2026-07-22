"""Composition root: wire DAOs -> services -> facades for injection."""
from __future__ import annotations

from functools import lru_cache

from risk_analytics_api.common.configuration import get_settings
from risk_analytics_api.daos.agent_config_gateway import PostgresAgentConfigGateway
from risk_analytics_api.daos.attention import PostgresAttentionDao
from risk_analytics_api.daos.connection import MongoDatabaseFactory, PostgresDatabase
from risk_analytics_api.daos.dashboard import PostgresDashboardDao
from risk_analytics_api.daos.evidence import MongoEvidenceDao
from risk_analytics_api.daos.graph_runs import PostgresGraphRunDao
from risk_analytics_api.daos.investigations import PostgresInvestigationDao
from risk_analytics_api.daos.reports import PostgresReportDao
from risk_analytics_api.daos.risk_findings import PostgresRiskFindingDao
from risk_analytics_api.facades.get_analysis_run import GetAnalysisRunFacade
from risk_analytics_api.facades.get_attention_feed import GetAttentionFeedFacade
from risk_analytics_api.facades.get_dashboard_activity import GetDashboardActivityFacade
from risk_analytics_api.facades.get_investigation import GetInvestigationFacade
from risk_analytics_api.facades.investigate_project import InvestigateProjectFacade
from risk_analytics_api.facades.list_analysis_runs import ListAnalysisRunsFacade
from risk_analytics_api.facades.list_investigation_templates import (
    ListInvestigationTemplatesFacade,
)
from risk_analytics_api.facades.list_investigations import ListInvestigationsFacade
from risk_analytics_api.facades.start_portfolio_analysis import StartPortfolioAnalysisFacade
from risk_analytics_api.facades.start_project_analysis import StartProjectAnalysisFacade
from risk_analytics_api.graphs.project_risk_manager import build_agent as build_specialist
from risk_analytics_api.services.analysis_orchestration import (
    DefaultAnalysisOrchestrationService,
)
from risk_analytics_api.services.attention import DefaultAttentionService
from risk_analytics_api.services.dashboard import DefaultDashboardService
from risk_analytics_api.services.evidence_retrieval import DefaultEvidenceRetrievalService
from risk_analytics_api.services.investigation import DefaultInvestigationService


@lru_cache
def get_postgres() -> PostgresDatabase:
    return PostgresDatabase(get_settings())


@lru_cache
def get_mongo() -> MongoDatabaseFactory:
    return MongoDatabaseFactory(get_settings())


def _orchestration_service() -> DefaultAnalysisOrchestrationService:
    pg = get_postgres()
    findings_dao = PostgresRiskFindingDao(pg)
    reports_dao = PostgresReportDao(pg)
    return DefaultAnalysisOrchestrationService(
        evidence_service=DefaultEvidenceRetrievalService(MongoEvidenceDao(get_mongo())),
        agent_config_gateway=PostgresAgentConfigGateway(pg),
        graph_run_dao=PostgresGraphRunDao(pg, findings_dao, reports_dao),
        risk_finding_dao=findings_dao,
        report_dao=reports_dao,
        agent_factory=build_specialist,
        settings=get_settings(),
    )


def provide_start_project_analysis_facade() -> StartProjectAnalysisFacade:
    return StartProjectAnalysisFacade(_orchestration_service())


def provide_start_portfolio_analysis_facade() -> StartPortfolioAnalysisFacade:
    return StartPortfolioAnalysisFacade(_orchestration_service())


def provide_get_analysis_run_facade() -> GetAnalysisRunFacade:
    return GetAnalysisRunFacade(_orchestration_service())


def provide_list_analysis_runs_facade() -> ListAnalysisRunsFacade:
    return ListAnalysisRunsFacade(_orchestration_service())


def _investigation_service() -> DefaultInvestigationService:
    return DefaultInvestigationService(
        mongo=get_mongo(),
        agent_config_gateway=PostgresAgentConfigGateway(get_postgres()),
        settings=get_settings(),
        investigations_dao=PostgresInvestigationDao(get_postgres()),
    )


def provide_investigate_project_facade() -> InvestigateProjectFacade:
    return InvestigateProjectFacade(_investigation_service())


def provide_list_investigations_facade() -> ListInvestigationsFacade:
    return ListInvestigationsFacade(_investigation_service())


def provide_get_investigation_facade() -> GetInvestigationFacade:
    return GetInvestigationFacade(_investigation_service())


def provide_list_investigation_templates_facade() -> ListInvestigationTemplatesFacade:
    return ListInvestigationTemplatesFacade(_investigation_service())


def provide_get_dashboard_activity_facade() -> GetDashboardActivityFacade:
    return GetDashboardActivityFacade(
        DefaultDashboardService(PostgresDashboardDao(get_postgres()))
    )


def provide_get_attention_feed_facade() -> GetAttentionFeedFacade:
    return GetAttentionFeedFacade(
        DefaultAttentionService(PostgresAttentionDao(get_postgres()))
    )
