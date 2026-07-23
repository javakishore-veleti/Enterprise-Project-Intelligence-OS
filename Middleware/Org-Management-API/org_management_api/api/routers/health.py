"""Liveness and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from org_management_api.api.dependencies import get_database
from org_management_api.common.configuration import get_settings
from org_management_api.daos.connection import Database
from org_management_api.dtos.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse, operation_id="getLiveness")
def liveness() -> HealthResponse:
    return HealthResponse(status="ok", service=get_settings().service_name)


@router.get("/health/ready", response_model=HealthResponse, operation_id="getReadiness")
def readiness(database: Database = Depends(get_database)) -> HealthResponse:
    try:
        database.ping()
        db_status = "ok"
        status = "ok"
    except Exception:
        db_status = "unavailable"
        status = "degraded"
    return HealthResponse(
        status=status,
        service=get_settings().service_name,
        dependencies={"postgresql": db_status},
    )
