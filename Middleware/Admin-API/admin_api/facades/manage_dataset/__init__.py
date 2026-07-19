"""Use case: view/trigger the Initial Dataset download (proxied to Ingestion API)."""
from __future__ import annotations

from admin_api.dtos.dataset import DatasetStatusResponse
from admin_api.interfaces.daos import DatasetGateway


class ManageDatasetFacade:
    def __init__(self, gateway: DatasetGateway, dataset_id: str) -> None:
        self._gateway = gateway
        self._dataset_id = dataset_id

    def status(self) -> DatasetStatusResponse:
        return self._gateway.get_status(self._dataset_id)

    def download(self) -> DatasetStatusResponse:
        return self._gateway.trigger_download(self._dataset_id)
