"""Dataset batch-ingestion endpoints (trigger + progress + DAG callbacks)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from ingestion_api.api.dependencies import provide_manage_ingestion_facade
from ingestion_api.dtos.requests import (
    ReportBatchProgressRequest,
    StartDatasetIngestionRequest,
    UpdateRunStatusRequest,
)
from ingestion_api.dtos.responses import IngestionProgressResponse, IngestionRunResponse
from ingestion_api.facades.manage_ingestion import ManageIngestionFacade

router = APIRouter(tags=["ingestion"])

Facade = Depends(provide_manage_ingestion_facade)


@router.post("/api/v1/ingestion/datasets/{dataset_id}/ingest",
             response_model=IngestionProgressResponse,
             status_code=status.HTTP_202_ACCEPTED, operation_id="startDatasetIngestion")
def start_ingestion(dataset_id: str, request: StartDatasetIngestionRequest,
                    facade: ManageIngestionFacade = Facade):
    return facade.start(dataset_id, request)


@router.get("/api/v1/ingestion/datasets/{dataset_id}/ingestion",
            response_model=IngestionProgressResponse, operation_id="getDatasetIngestionProgress")
def get_ingestion_progress(dataset_id: str, facade: ManageIngestionFacade = Facade):
    return facade.progress(dataset_id)


@router.post("/api/v1/ingestion/runs/{run_id}/progress",
             status_code=status.HTTP_204_NO_CONTENT, operation_id="reportBatchProgress")
def report_batch_progress(run_id: str, request: ReportBatchProgressRequest,
                          facade: ManageIngestionFacade = Facade):
    """Per-batch checkpoint + progress event posted by the ingest DAG."""
    facade.report_batch(run_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/api/v1/ingestion/runs/{run_id}/status",
            response_model=IngestionRunResponse, operation_id="finalizeIngestionRun")
def finalize_run(run_id: str, request: UpdateRunStatusRequest,
                 facade: ManageIngestionFacade = Facade):
    """Run-level status finalization posted by the ingest DAG."""
    return facade.finalize_run(run_id, request)


@router.get("/api/v1/ingestion/runs/{run_id}/entities/{entity}/committed-batches",
            operation_id="getCommittedBatches")
def committed_batches(run_id: str, entity: str, facade: ManageIngestionFacade = Facade):
    """Batch numbers already committed for (run, entity) — the DAG skips these to resume."""
    return {"run_id": run_id, "entity": entity, "batch_numbers": facade.committed_batches(run_id, entity)}
