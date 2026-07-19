"""Ingestion run endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ingestion_api.api.dependencies import (
    provide_get_ingestion_status_facade,
    provide_start_ingestion_facade,
)
from ingestion_api.dtos.requests import StartIngestionRequest
from ingestion_api.dtos.responses import IngestionRunResponse
from ingestion_api.facades.get_ingestion_status import GetIngestionStatusFacade
from ingestion_api.facades.start_ingestion import StartIngestionFacade

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


@router.post(
    "/runs",
    response_model=IngestionRunResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="startIngestion",
)
def start_ingestion(
    request: StartIngestionRequest,
    facade: StartIngestionFacade = Depends(provide_start_ingestion_facade),
) -> IngestionRunResponse:
    return facade.execute(request)


@router.get(
    "/runs/{run_id}",
    response_model=IngestionRunResponse,
    operation_id="getIngestionStatus",
)
def get_ingestion_status(
    run_id: str,
    facade: GetIngestionStatusFacade = Depends(provide_get_ingestion_status_facade),
) -> IngestionRunResponse:
    return facade.execute(run_id)
