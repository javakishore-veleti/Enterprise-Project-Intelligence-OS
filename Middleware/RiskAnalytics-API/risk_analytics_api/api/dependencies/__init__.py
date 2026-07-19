"""Composition root: wire DAOs -> services -> facades for injection."""
from __future__ import annotations

from functools import lru_cache

from risk_analytics_api.common.configuration import get_settings
from risk_analytics_api.daos.agent_config_gateway import PostgresAgentConfigGateway
from risk_analytics_api.daos.connection import MongoDatabaseFactory, PostgresDatabase
from risk_analytics_api.daos.evidence import MongoEvidenceDao
from risk_analytics_api.daos.graph_runs import PostgresGraphRunDao
from risk_analytics_api.daos.reports import PostgresReportDao
from risk_analytics_api.daos.risk_findings import PostgresRiskFindingDao
from risk_analytics_api.facades.get_analysis_run import GetAnalysisRunFacade
from risk_analytics_api.facades.start_project_analysis import StartProjectAnalysisFacade
from risk_analytics_api.graphs.project_risk_manager import build_agent as build_specialist
from risk_analytics_api.services.analysis_orchestration import (
    DefaultAnalysisOrchestrationService,
)
from risk_analytics_api.services.evidence_retrieval import DefaultEvidenceRetrievalService


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


def provide_get_analysis_run_facade() -> GetAnalysisRunFacade:
    return GetAnalysisRunFacade(_orchestration_service())
