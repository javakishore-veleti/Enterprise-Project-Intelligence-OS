"""Liveness and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from risk_analytics_api.api.dependencies import get_mongo, get_postgres
from risk_analytics_api.common.configuration import get_settings
from risk_analytics_api.daos.connection import MongoDatabaseFactory, PostgresDatabase
from risk_analytics_api.dtos.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse, operation_id="getLiveness")
def liveness() -> HealthResponse:
    return HealthResponse(status="ok", service=get_settings().service_name)


@router.get("/health/ready", response_model=HealthResponse, operation_id="getReadiness")
def readiness(
    postgres: PostgresDatabase = Depends(get_postgres),
    mongo: MongoDatabaseFactory = Depends(get_mongo),
) -> HealthResponse:
    deps: dict[str, str] = {}
    ok = True
    for name, check in (("postgresql", postgres.ping), ("mongodb", mongo.ping)):
        try:
            check()
            deps[name] = "ok"
        except Exception:
            deps[name] = "unavailable"
            ok = False
    return HealthResponse(
        status="ok" if ok else "degraded",
        service=get_settings().service_name,
        dependencies=deps,
    )
