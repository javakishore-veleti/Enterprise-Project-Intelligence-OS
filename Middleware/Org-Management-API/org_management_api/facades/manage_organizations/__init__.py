"""Use case: manage the organization tree.

Translates internal OrganizationRecords into the public OrganizationResponse
shape (including the 1-indexed `level`, root = 1).
"""
from __future__ import annotations

from org_management_api.dtos.common import OrganizationRecord
from org_management_api.dtos.requests import (
    CreateOrganizationRequest,
    MoveOrganizationRequest,
    UpdateOrganizationRequest,
)
from org_management_api.dtos.responses import (
    OrganizationListResponse,
    OrganizationResponse,
)
from org_management_api.interfaces.services import OrganizationService


def _response(rec: OrganizationRecord) -> OrganizationResponse:
    return OrganizationResponse(
        org_id=rec.org_id,
        parent_org_id=rec.parent_org_id,
        root_org_id=rec.root_org_id,
        path=rec.path,
        depth=rec.depth,
        level=rec.level,
        name=rec.name,
        kind=rec.kind,
        status=rec.status,
        created_at=rec.created_at,
    )


def _list(records: list[OrganizationRecord]) -> OrganizationListResponse:
    return OrganizationListResponse(organizations=[_response(r) for r in records])


class ManageOrganizationsFacade:
    def __init__(self, service: OrganizationService) -> None:
        self._service = service

    def create(self, request: CreateOrganizationRequest) -> OrganizationResponse:
        return _response(self._service.create(request))

    def get(self, org_id: str) -> OrganizationResponse:
        return _response(self._service.get(org_id))

    def children(self, org_id: str) -> OrganizationListResponse:
        return _list(self._service.children(org_id))

    def subtree(self, org_id: str) -> OrganizationListResponse:
        return _list(self._service.subtree(org_id))

    def ancestors(self, org_id: str) -> OrganizationListResponse:
        return _list(self._service.ancestors(org_id))

    def update(self, org_id: str, request: UpdateOrganizationRequest) -> OrganizationResponse:
        return _response(self._service.update(org_id, request))

    def move(self, org_id: str, request: MoveOrganizationRequest) -> OrganizationResponse:
        return _response(self._service.move(org_id, request))

    def list_roots(self) -> OrganizationListResponse:
        return _list(self._service.list_roots())

    def list_tenant(self, root_org_id: str) -> OrganizationListResponse:
        return _list(self._service.list_tenant(root_org_id))
