"""Composition root: wire DAOs -> services -> facades for injection."""
from __future__ import annotations

from functools import lru_cache

from projects_api.common.configuration import get_settings
from projects_api.daos.connection import Database
from projects_api.daos.forecast_subjects import MongoForecastSubjectsDao
from projects_api.daos.metrics_computation import MongoMetricsComputationDao
from projects_api.daos.project_assignments import MongoProjectAssignmentsDao
from projects_api.daos.portfolio_summary import MongoPortfolioSummaryDao
from projects_api.daos.project_groups import MongoProjectGroupsDao
from projects_api.daos.project_metrics import MongoProjectMetricsDao
from projects_api.daos.projects import MongoProjectsDao
from projects_api.facades.compute_metrics import ComputeMetricsFacade
from projects_api.facades.forecast_subjects import ForecastSubjectsFacade
from projects_api.facades.get_project import GetProjectFacade
from projects_api.facades.get_project_metrics import GetProjectMetricsFacade
from projects_api.facades.portfolio_summary import PortfolioSummaryFacade
from projects_api.facades.project_groups import ProjectGroupsFacade
from projects_api.facades.search_projects import SearchProjectsFacade
from projects_api.services.forecast_subjects import DefaultForecastSubjectsService
from projects_api.services.metrics_computation import DefaultMetricsComputationService
from projects_api.services.portfolio_summary import DefaultPortfolioSummaryService
from projects_api.services.project_groups import DefaultProjectGroupsService
from projects_api.services.project_metrics import DefaultProjectMetricsService
from projects_api.services.project_query import DefaultProjectQueryService


@lru_cache
def get_database() -> Database:
    return Database(get_settings())


def _query_service() -> DefaultProjectQueryService:
    return DefaultProjectQueryService(MongoProjectsDao(get_database()), get_settings())


def _metrics_service() -> DefaultProjectMetricsService:
    return DefaultProjectMetricsService(MongoProjectMetricsDao(get_database()))


def provide_search_projects_facade() -> SearchProjectsFacade:
    return SearchProjectsFacade(_query_service())


def provide_get_project_facade() -> GetProjectFacade:
    return GetProjectFacade(_query_service())


def provide_get_project_metrics_facade() -> GetProjectMetricsFacade:
    return GetProjectMetricsFacade(_metrics_service())


def provide_compute_metrics_facade() -> ComputeMetricsFacade:
    db = get_database()
    service = DefaultMetricsComputationService(
        MongoMetricsComputationDao(db), MongoProjectsDao(db))
    return ComputeMetricsFacade(service)


def provide_forecast_subjects_facade() -> ForecastSubjectsFacade:
    db = get_database()
    service = DefaultForecastSubjectsService(
        MongoForecastSubjectsDao(db), MongoProjectsDao(db))
    return ForecastSubjectsFacade(service)


def provide_portfolio_summary_facade() -> PortfolioSummaryFacade:
    db = get_database()
    service = DefaultPortfolioSummaryService(MongoPortfolioSummaryDao(db))
    return PortfolioSummaryFacade(service, MongoProjectAssignmentsDao(db))


def provide_project_groups_facade() -> ProjectGroupsFacade:
    service = DefaultProjectGroupsService(MongoProjectGroupsDao(get_database()))
    return ProjectGroupsFacade(service)
