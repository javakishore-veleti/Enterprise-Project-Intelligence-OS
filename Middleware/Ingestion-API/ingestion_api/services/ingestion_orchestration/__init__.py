"""Ingestion orchestration service — reusable ingestion-lifecycle rules."""
from __future__ import annotations

from ingestion_api.common.exceptions import NotFoundError
from ingestion_api.common.utilities import new_id, utc_now
from ingestion_api.dtos.common import IngestionStatus
from ingestion_api.dtos.requests import StartIngestionRequest
from ingestion_api.dtos.responses import IngestionRunResponse
from ingestion_api.interfaces.daos import AirflowGateway, IngestionTrackingDao
from ingestion_api.interfaces.services import IngestionOrchestrationService


class DefaultIngestionOrchestrationService(IngestionOrchestrationService):
    """Creates ingestion runs, persists them, and hands work to Airflow."""

    def __init__(self, tracking_dao: IngestionTrackingDao, airflow: AirflowGateway) -> None:
        self._tracking = tracking_dao
        self._airflow = airflow

    def start_run(self, request: StartIngestionRequest) -> IngestionRunResponse:
        now = utc_now()
        run = IngestionRunResponse(
            run_id=new_id(),
            dataset_id=request.dataset_id,
            status=IngestionStatus.PENDING,
            batch_size=request.batch_size,
            parallelism=request.parallelism,
            requested_by=request.requested_by,
            created_at=now,
            updated_at=now,
        )
        persisted = self._tracking.insert_run(run)
        # Cross the governed boundary into the operational scheduler.
        self._airflow.trigger_ingestion(persisted.run_id, persisted.dataset_id)
        return persisted

    def get_run(self, run_id: str) -> IngestionRunResponse:
        run = self._tracking.get_run(run_id)
        if run is None:
            raise NotFoundError(f"ingestion run '{run_id}' not found")
        return run
