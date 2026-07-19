"""Initial Dataset management endpoints (proxied to the Ingestion API)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from fastapi import status

from admin_api.api.dependencies import provide_manage_dataset_facade
from admin_api.dtos.dataset import DatasetStatusResponse, IngestionProgressResponse
from admin_api.facades.manage_dataset import ManageDatasetFacade

router = APIRouter(prefix="/api/v1/admin/dataset", tags=["dataset"])

_Facade = Depends(provide_manage_dataset_facade)


@router.get("/status", response_model=DatasetStatusResponse, operation_id="getDatasetStatus")
def get_dataset_status(facade: ManageDatasetFacade = _Facade):
    return facade.status()


@router.post("/download", response_model=DatasetStatusResponse, operation_id="downloadDataset")
def download_dataset(facade: ManageDatasetFacade = _Facade):
    """Trigger the Airflow-driven dataset download (via the Ingestion API)."""
    return facade.download()


@router.get("/ingestion", response_model=IngestionProgressResponse, operation_id="getDatasetIngestion")
def get_dataset_ingestion(facade: ManageDatasetFacade = _Facade):
    return facade.ingestion()


@router.post("/ingest", response_model=IngestionProgressResponse,
             status_code=status.HTTP_202_ACCEPTED, operation_id="ingestDataset")
def ingest_dataset(facade: ManageDatasetFacade = _Facade):
    """Trigger the Airflow-driven batch ingestion into the evidence store."""
    return facade.ingest()
