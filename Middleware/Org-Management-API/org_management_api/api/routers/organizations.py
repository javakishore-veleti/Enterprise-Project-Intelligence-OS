"""Organization tree endpoints (create / read / subtree / ancestors / move)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from org_management_api.api.dependencies import provide_manage_organizations_facade
from org_management_api.dtos.requests import (
    CreateOrganizationRequest,
    MoveOrganizationRequest,
    UpdateOrganizationRequest,
)
from org_management_api.dtos.responses import (
    OrganizationListResponse,
    OrganizationResponse,
)
from org_management_api.facades.manage_organizations import ManageOrganizationsFacade

router = APIRouter(prefix="/api/v1/orgs", tags=["organizations"])

Facade = Depends(provide_manage_organizations_facade)


@router.post("", response_model=OrganizationResponse,
             status_code=status.HTTP_201_CREATED, operation_id="createOrganization")
def create_organization(
    request: CreateOrganizationRequest, facade: ManageOrganizationsFacade = Facade
):
    return facade.create(request)


@router.get("", response_model=OrganizationListResponse, operation_id="listOrganizations")
def list_organizations(
    root: str | None = Query(default=None, description="Tenant root org id; omit for all roots."),
    facade: ManageOrganizationsFacade = Facade,
):
    # `?root=<id>` returns the whole tenant tree; no `root` returns all roots.
    return facade.list_tenant(root) if root else facade.list_roots()


@router.get("/{org_id}", response_model=OrganizationResponse, operation_id="getOrganization")
def get_organization(org_id: str, facade: ManageOrganizationsFacade = Facade):
    return facade.get(org_id)


@router.get("/{org_id}/children", response_model=OrganizationListResponse,
            operation_id="getOrganizationChildren")
def get_children(org_id: str, facade: ManageOrganizationsFacade = Facade):
    return facade.children(org_id)


@router.get("/{org_id}/subtree", response_model=OrganizationListResponse,
            operation_id="getOrganizationSubtree")
def get_subtree(org_id: str, facade: ManageOrganizationsFacade = Facade):
    return facade.subtree(org_id)


@router.get("/{org_id}/ancestors", response_model=OrganizationListResponse,
            operation_id="getOrganizationAncestors")
def get_ancestors(org_id: str, facade: ManageOrganizationsFacade = Facade):
    return facade.ancestors(org_id)


@router.put("/{org_id}", response_model=OrganizationResponse, operation_id="updateOrganization")
def update_organization(
    org_id: str, request: UpdateOrganizationRequest, facade: ManageOrganizationsFacade = Facade
):
    return facade.update(org_id, request)


@router.post("/{org_id}/move", response_model=OrganizationResponse,
             operation_id="moveOrganization")
def move_organization(
    org_id: str, request: MoveOrganizationRequest, facade: ManageOrganizationsFacade = Facade
):
    return facade.move(org_id, request)
