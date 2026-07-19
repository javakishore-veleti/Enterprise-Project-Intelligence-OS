"""Audit management service — read the administrative audit history."""
from __future__ import annotations

from admin_api.dtos.common import PageMeta
from admin_api.dtos.responses import AuditListResponse
from admin_api.interfaces.daos import AuditDao
from admin_api.interfaces.services import AuditManagementService


class DefaultAuditManagementService(AuditManagementService):
    def __init__(self, audit_dao: AuditDao) -> None:
        self._audit = audit_dao

    def list(self, limit: int, offset: int) -> AuditListResponse:
        items, total = self._audit.list(limit, offset)
        return AuditListResponse(
            items=items, page=PageMeta(total=total, limit=limit, offset=offset)
        )
