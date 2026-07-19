"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion_api.dtos.common import IngestionStatus
from ingestion_api.dtos.responses import IngestionRunResponse


class IngestionTrackingDao(ABC):
    """Persistence of ingestion-run operational state (PostgreSQL)."""

    @abstractmethod
    def insert_run(self, run: IngestionRunResponse) -> IngestionRunResponse: ...

    @abstractmethod
    def get_run(self, run_id: str) -> IngestionRunResponse | None: ...

    @abstractmethod
    def update_status(self, run_id: str, status: IngestionStatus) -> IngestionRunResponse | None: ...


class AirflowGateway(ABC):
    """Gateway that triggers operational workflows in Apache Airflow.

    Agent/reasoning logic never lives here — this only hands ingestion work off
    to the operational scheduler across the governed boundary.
    """

    @abstractmethod
    def trigger_ingestion(self, run_id: str, dataset_id: str) -> str:
        """Trigger the ingestion DAG; return the external run reference."""
