"""Use case: dataset batch ingestion (trigger + progress + DAG callbacks)."""
from __future__ import annotations

from ingestion_api.dtos.requests import (
    ReportBatchProgressRequest,
    StartDatasetIngestionRequest,
    UpdateRunStatusRequest,
)
from ingestion_api.dtos.responses import IngestionProgressResponse, IngestionRunResponse
from ingestion_api.interfaces.services import DatasetIngestionService


class ManageIngestionFacade:
    def __init__(self, service: DatasetIngestionService) -> None:
        self._service = service

    def start(self, dataset_id: str, request: StartDatasetIngestionRequest) -> IngestionProgressResponse:
        return self._service.start(dataset_id, request)

    def progress(self, dataset_id: str) -> IngestionProgressResponse:
        return self._service.progress(dataset_id)

    def report_batch(self, run_id: str, request: ReportBatchProgressRequest) -> None:
        self._service.report_batch(run_id, request)

    def finalize_run(self, run_id: str, request: UpdateRunStatusRequest) -> IngestionRunResponse:
        return self._service.finalize_run(run_id, request)

    def committed_batches(self, run_id: str, entity: str) -> list[int]:
        return self._service.committed_batches(run_id, entity)
