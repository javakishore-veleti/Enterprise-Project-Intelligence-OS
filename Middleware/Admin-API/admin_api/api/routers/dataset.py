"""Initial Dataset management endpoints (proxied to the Ingestion API)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from admin_api.api.dependencies import provide_manage_dataset_facade
from admin_api.dtos.dataset import DatasetStatusResponse
from admin_api.facades.manage_dataset import ManageDatasetFacade

router = APIRouter(prefix="/api/v1/admin/dataset", tags=["dataset"])


@router.get("/status", response_model=DatasetStatusResponse, operation_id="getDatasetStatus")
def get_dataset_status(facade: ManageDatasetFacade = Depends(provide_manage_dataset_facade)):
    return facade.status()


@router.post("/download", response_model=DatasetStatusResponse, operation_id="downloadDataset")
def download_dataset(facade: ManageDatasetFacade = Depends(provide_manage_dataset_facade)):
    """Trigger the Airflow-driven dataset download (via the Ingestion API)."""
    return facade.download()
