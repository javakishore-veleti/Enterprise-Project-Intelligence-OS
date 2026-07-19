"""Audit-history and system-health endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from admin_api.api.dependencies import (
    provide_get_audit_history_facade,
    provide_get_system_health_facade,
)
from admin_api.dtos.responses import AuditListResponse, SystemHealthResponse
from admin_api.facades.get_audit_history import GetAuditHistoryFacade
from admin_api.facades.get_system_health import GetSystemHealthFacade

router = APIRouter(prefix="/api/v1/admin", tags=["system"])


@router.get("/audit", response_model=AuditListResponse, operation_id="getAuditHistory")
def get_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: GetAuditHistoryFacade = Depends(provide_get_audit_history_facade),
) -> AuditListResponse:
    return facade.execute(limit, offset)


@router.get("/system/health", response_model=SystemHealthResponse, operation_id="getSystemHealth")
def get_system_health(
    facade: GetSystemHealthFacade = Depends(provide_get_system_health_facade),
) -> SystemHealthResponse:
    return facade.execute()
