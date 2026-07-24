"""Use case: read administrative audit history."""
from __future__ import annotations

from admin_api.dtos.responses import AuditListResponse
from admin_api.interfaces.facades import GetAuditHistoryUseCase
from admin_api.interfaces.services import AuditManagementService


class GetAuditHistoryFacade(GetAuditHistoryUseCase):
    def __init__(self, service: AuditManagementService) -> None:
        self._service = service

    def execute(self, limit: int, offset: int, q: str | None = None) -> AuditListResponse:
        return self._service.list(limit, offset, q)
