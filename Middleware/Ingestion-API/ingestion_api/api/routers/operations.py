"""Dataset operational sub-operation endpoints (called by Airflow DAGs).

Each operation runs synchronously and completes; the DAGs POST then poll GET.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ingestion_api.api.dependencies import provide_dataset_operations_facade
from ingestion_api.dtos.requests import (
    AcquireDatasetRequest,
    IndexDatasetRequest,
    ReconcileDatasetRequest,
    ValidateDatasetRequest,
    VerifyAcquisitionRequest,
)
from ingestion_api.dtos.responses import (
    AcquisitionExtractResponse,
    AcquisitionResponse,
    AcquisitionVerifyResponse,
    IndexResponse,
    ReconciliationResponse,
    ValidationResponse,
)
from ingestion_api.facades.dataset_operations import DatasetOperationsFacade

router = APIRouter(prefix="/api/v1/ingestion", tags=["operations"])

Facade = Depends(provide_dataset_operations_facade)


# --- acquisitions ---
@router.post("/acquisitions", response_model=AcquisitionResponse,
             status_code=status.HTTP_201_CREATED, operation_id="startAcquisition")
def start_acquisition(request: AcquireDatasetRequest, facade: DatasetOperationsFacade = Facade):
    return facade.acquire(request)


@router.get("/acquisitions/{acquisition_id}", response_model=AcquisitionResponse,
            operation_id="getAcquisition")
def get_acquisition(acquisition_id: str, facade: DatasetOperationsFacade = Facade):
    return facade.get_acquisition(acquisition_id)


@router.post("/acquisitions/{acquisition_id}/verify", response_model=AcquisitionVerifyResponse,
             operation_id="verifyAcquisition")
def verify_acquisition(acquisition_id: str, request: VerifyAcquisitionRequest,
                       facade: DatasetOperationsFacade = Facade):
    return facade.verify_acquisition(acquisition_id, request)


@router.post("/acquisitions/{acquisition_id}/extract", response_model=AcquisitionExtractResponse,
             operation_id="extractAcquisition")
def extract_acquisition(acquisition_id: str, facade: DatasetOperationsFacade = Facade):
    return facade.extract_acquisition(acquisition_id)


# --- validations ---
@router.post("/validations", response_model=ValidationResponse,
             status_code=status.HTTP_201_CREATED, operation_id="startValidation")
def start_validation(request: ValidateDatasetRequest, facade: DatasetOperationsFacade = Facade):
    return facade.validate(request)


@router.get("/validations/{validation_id}", response_model=ValidationResponse,
            operation_id="getValidation")
def get_validation(validation_id: str, facade: DatasetOperationsFacade = Facade):
    return facade.get_validation(validation_id)


# --- indexes ---
@router.post("/indexes", response_model=IndexResponse,
             status_code=status.HTTP_201_CREATED, operation_id="startIndexing")
def start_indexing(request: IndexDatasetRequest, facade: DatasetOperationsFacade = Facade):
    return facade.create_indexes(request)


@router.get("/indexes/{index_job_id}", response_model=IndexResponse, operation_id="getIndexing")
def get_indexing(index_job_id: str, facade: DatasetOperationsFacade = Facade):
    return facade.get_index(index_job_id)


# --- reconciliations ---
@router.post("/reconciliations", response_model=ReconciliationResponse,
             status_code=status.HTTP_201_CREATED, operation_id="startReconciliation")
def start_reconciliation(request: ReconcileDatasetRequest, facade: DatasetOperationsFacade = Facade):
    return facade.reconcile(request)


@router.get("/reconciliations/{reconciliation_id}", response_model=ReconciliationResponse,
            operation_id="getReconciliation")
def get_reconciliation(reconciliation_id: str, facade: DatasetOperationsFacade = Facade):
    return facade.get_reconciliation(reconciliation_id)
