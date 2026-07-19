"""Use case: manage dataset acquisition (status + trigger download)."""
from __future__ import annotations

from ingestion_api.dtos.requests import UpdateDatasetStatusRequest
from ingestion_api.dtos.responses import DatasetStatusResponse
from ingestion_api.interfaces.services import DatasetService


class ManageDatasetFacade:
    def __init__(self, service: DatasetService) -> None:
        self._service = service

    def get_status(self, dataset_id: str) -> DatasetStatusResponse:
        return self._service.get_status(dataset_id)

    def request_download(self, dataset_id: str) -> DatasetStatusResponse:
        return self._service.request_download(dataset_id)

    def update_status(self, dataset_id: str, request: UpdateDatasetStatusRequest) -> DatasetStatusResponse:
        return self._service.update_status(dataset_id, request)
