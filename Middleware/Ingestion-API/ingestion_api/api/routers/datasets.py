"""Dataset acquisition endpoints (status + trigger download + DAG status updates)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ingestion_api.api.dependencies import provide_manage_dataset_facade
from ingestion_api.dtos.requests import UpdateDatasetStatusRequest
from ingestion_api.dtos.responses import DatasetStatusResponse
from ingestion_api.facades.manage_dataset import ManageDatasetFacade

router = APIRouter(prefix="/api/v1/ingestion/datasets", tags=["datasets"])

Facade = Depends(provide_manage_dataset_facade)


@router.get("/{dataset_id}", response_model=DatasetStatusResponse, operation_id="getDatasetStatus")
def get_dataset_status(dataset_id: str, facade: ManageDatasetFacade = Facade):
    return facade.get_status(dataset_id)


@router.post("/{dataset_id}/acquire", response_model=DatasetStatusResponse,
             status_code=status.HTTP_202_ACCEPTED, operation_id="acquireDataset")
def acquire_dataset(dataset_id: str, facade: ManageDatasetFacade = Facade):
    """Trigger the Airflow acquire DAG and mark the dataset DOWNLOADING."""
    return facade.request_download(dataset_id)


@router.put("/{dataset_id}/status", response_model=DatasetStatusResponse,
            operation_id="updateDatasetStatus")
def update_dataset_status(dataset_id: str, request: UpdateDatasetStatusRequest,
                          facade: ManageDatasetFacade = Facade):
    """State updates posted by the Airflow acquire DAG as it downloads."""
    return facade.update_status(dataset_id, request)
