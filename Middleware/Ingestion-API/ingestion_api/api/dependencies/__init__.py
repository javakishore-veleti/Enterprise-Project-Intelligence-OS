"""Composition root: wire DAOs -> services -> facades for injection.

Routers depend on facades via these providers. Assembly lives here so the
layered wiring is declared in exactly one place.
"""
from __future__ import annotations

from functools import lru_cache

from ingestion_api.common.configuration import Settings, get_settings
from ingestion_api.daos.airflow_gateway import HttpAirflowGateway
from ingestion_api.daos.airflow_gateway.dataset_acquisition import AirflowDatasetAcquisitionGateway
from ingestion_api.daos.connection import Database
from ingestion_api.daos.datasets import PostgresDatasetsDao
from ingestion_api.daos.evidence_counts import MongoEvidenceCountsGateway
from ingestion_api.daos.ingestion_tracking import PostgresIngestionTrackingDao
from ingestion_api.daos.operations import PostgresOperationsDao
from ingestion_api.facades.dataset_operations import DatasetOperationsFacade
from ingestion_api.facades.get_ingestion_status import GetIngestionStatusFacade
from ingestion_api.facades.manage_dataset import ManageDatasetFacade
from ingestion_api.facades.start_ingestion import StartIngestionFacade
from ingestion_api.services.datasets import DefaultDatasetService
from ingestion_api.services.ingestion_orchestration import (
    DefaultIngestionOrchestrationService,
)
from ingestion_api.services.operations import DefaultOperationsService


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


@lru_cache
def get_evidence_counts() -> MongoEvidenceCountsGateway:
    return MongoEvidenceCountsGateway(get_settings())


def provide_dataset_operations_facade() -> DatasetOperationsFacade:
    service = DefaultOperationsService(PostgresOperationsDao(get_database()), get_evidence_counts())
    return DatasetOperationsFacade(service)


def provide_manage_dataset_facade() -> ManageDatasetFacade:
    settings = get_settings()
    service = DefaultDatasetService(
        PostgresDatasetsDao(get_database()),
        AirflowDatasetAcquisitionGateway(settings),
    )
    return ManageDatasetFacade(service)
