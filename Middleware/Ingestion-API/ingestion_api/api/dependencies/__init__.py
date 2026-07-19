"""Composition root: wire DAOs -> services -> facades for injection.

Routers depend on facades via these providers. Assembly lives here so the
layered wiring is declared in exactly one place.
"""
from __future__ import annotations

from functools import lru_cache

from ingestion_api.common.configuration import Settings, get_settings
from ingestion_api.daos.airflow_gateway import HttpAirflowGateway
from ingestion_api.daos.connection import Database
from ingestion_api.daos.ingestion_tracking import PostgresIngestionTrackingDao
from ingestion_api.facades.get_ingestion_status import GetIngestionStatusFacade
from ingestion_api.facades.start_ingestion import StartIngestionFacade
from ingestion_api.services.ingestion_orchestration import (
    DefaultIngestionOrchestrationService,
)


@lru_cache
def get_database() -> Database:
    return Database(get_settings())


def _service(settings: Settings) -> DefaultIngestionOrchestrationService:
    database = get_database()
    tracking = PostgresIngestionTrackingDao(database)
    airflow = HttpAirflowGateway(settings)
    return DefaultIngestionOrchestrationService(tracking, airflow)


def provide_start_ingestion_facade() -> StartIngestionFacade:
    return StartIngestionFacade(_service(get_settings()))


def provide_get_ingestion_status_facade() -> GetIngestionStatusFacade:
    return GetIngestionStatusFacade(_service(get_settings()))
