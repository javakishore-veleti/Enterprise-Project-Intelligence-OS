"""Liveness and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from projects_api.api.dependencies import get_database
from projects_api.common.configuration import get_settings
from projects_api.daos.connection import Database
from projects_api.dtos.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse, operation_id="getLiveness")
def liveness() -> HealthResponse:
    return HealthResponse(status="ok", service=get_settings().service_name)


@router.get("/health/ready", response_model=HealthResponse, operation_id="getReadiness")
def readiness(database: Database = Depends(get_database)) -> HealthResponse:
    try:
        database.ping()
        db_status, status = "ok", "ok"
    except Exception:
        db_status, status = "unavailable", "degraded"
    return HealthResponse(
        status=status,
        service=get_settings().service_name,
        dependencies={"mongodb": db_status},
    )
