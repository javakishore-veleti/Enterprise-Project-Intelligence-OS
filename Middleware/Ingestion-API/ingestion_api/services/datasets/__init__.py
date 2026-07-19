"""Dataset service — acquisition status + triggering the Airflow download DAG."""
from __future__ import annotations

from ingestion_api.common.exceptions import NotFoundError
from ingestion_api.common.logging import get_logger
from ingestion_api.dtos.common import DatasetState
from ingestion_api.dtos.requests import UpdateDatasetStatusRequest
from ingestion_api.dtos.responses import DatasetStatusResponse
from ingestion_api.interfaces.daos import DatasetAcquisitionGateway, DatasetsDao
from ingestion_api.interfaces.services import DatasetService

_logger = get_logger(__name__)


class DefaultDatasetService(DatasetService):
    def __init__(self, datasets_dao: DatasetsDao, acquire_gateway: DatasetAcquisitionGateway) -> None:
        self._dao = datasets_dao
        self._airflow = acquire_gateway

    def get_status(self, dataset_id: str) -> DatasetStatusResponse:
        status = self._dao.get(dataset_id)
        if status is None:
            raise NotFoundError(f"dataset '{dataset_id}' not found")
        return status

    def request_download(self, dataset_id: str) -> DatasetStatusResponse:
        status = self.get_status(dataset_id)
        # Idempotent: already downloaded or in progress -> return current state, no re-trigger.
        if status.state in (DatasetState.DOWNLOADED.value, DatasetState.DOWNLOADING.value):
            return status

        # Trigger the Airflow acquire DAG first; only mark DOWNLOADING if it accepts.
        dag_run = self._airflow.trigger_acquire(dataset_id)  # raises 503 if Airflow is down
        updated = self._dao.update_status(
            dataset_id, DatasetState.DOWNLOADING.value,
            downloaded_bytes=0, message=f"Download triggered (Airflow run {dag_run}).",
        )
        _logger.info("dataset download requested", extra={"context": {
            "dataset_id": dataset_id, "dag_run": dag_run}})
        return updated

    def update_status(self, dataset_id: str, request: UpdateDatasetStatusRequest) -> DatasetStatusResponse:
        self.get_status(dataset_id)  # 404 if unknown
        downloaded = request.state == DatasetState.DOWNLOADED.value
        updated = self._dao.update_status(
            dataset_id, request.state,
            downloaded_bytes=request.downloaded_bytes,
            downloaded_path=request.downloaded_path,
            message=request.message,
            set_downloaded_at=downloaded,
        )
        return updated
