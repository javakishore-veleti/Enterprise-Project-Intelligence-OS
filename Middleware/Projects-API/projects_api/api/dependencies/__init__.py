"""Composition root: wire DAOs -> services -> facades for injection."""
from __future__ import annotations

from functools import lru_cache

from projects_api.common.configuration import get_settings
from projects_api.daos.connection import Database
from projects_api.daos.project_metrics import MongoProjectMetricsDao
from projects_api.daos.projects import MongoProjectsDao
from projects_api.facades.get_project import GetProjectFacade
from projects_api.facades.get_project_metrics import GetProjectMetricsFacade
from projects_api.facades.search_projects import SearchProjectsFacade
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
