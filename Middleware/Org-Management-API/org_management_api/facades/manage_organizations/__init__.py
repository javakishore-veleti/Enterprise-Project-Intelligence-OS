"""Use case: manage the organization tree.

Translates internal OrganizationRecords into the public OrganizationResponse
shape (including the 1-indexed `level`, root = 1).
"""
from __future__ import annotations

from org_management_api.dtos.common import OrganizationPage, OrganizationRecord
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
        child_count=rec.child_count,
        member_count=rec.member_count,
    )


def _list(records: list[OrganizationRecord]) -> OrganizationListResponse:
    return OrganizationListResponse(organizations=[_response(r) for r in records])


def _page(page: OrganizationPage) -> OrganizationListResponse:
    return OrganizationListResponse(
        organizations=[_response(r) for r in page.organizations],
        total=page.total,
        returned=len(page.organizations),
        offset=page.offset,
        limit=page.limit,
    )


class ManageOrganizationsFacade:
    def __init__(self, service: OrganizationService) -> None:
        self._service = service

    def create(self, request: CreateOrganizationRequest) -> OrganizationResponse:
        return _response(self._service.create(request))

    def get(self, org_id: str) -> OrganizationResponse:
        return _response(self._service.get(org_id))

    def children(
        self,
        org_id: str,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        sort: str = "name",
    ) -> OrganizationListResponse:
        return _page(self._service.children(org_id, limit, offset, q, sort))

    def search(
        self, q: str, root: str | None, limit: int, offset: int
    ) -> OrganizationListResponse:
        return _page(self._service.search(q, root, limit, offset))

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
