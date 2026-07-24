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


# NOTE: declared BEFORE `/{org_id}` so the literal `/search` path is not captured
# as an org id by the parameterized route.
@router.get("/search", response_model=OrganizationListResponse, operation_id="searchOrganizations")
def search_organizations(
    q: str = Query(..., min_length=1, description="Case-insensitive substring match on org name."),
    root: str | None = Query(default=None, description="Restrict to one tenant (root_org_id)."),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: ManageOrganizationsFacade = Facade,
):
    return facade.search(q, root, limit, offset)


@router.get("/{org_id}", response_model=OrganizationResponse, operation_id="getOrganization")
def get_organization(org_id: str, facade: ManageOrganizationsFacade = Facade):
    return facade.get(org_id)


@router.get("/{org_id}/children", response_model=OrganizationListResponse,
            operation_id="getOrganizationChildren")
def get_children(
    org_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(
        default=None, description="Case-insensitive substring filter on the DIRECT child names."),
    sort: str = Query(
        default="name", pattern="^(name|created_at|child_count)$",
        description="Order key: name (A→Z), created_at (newest first), child_count (most sub-orgs first)."),
    facade: ManageOrganizationsFacade = Facade,
):
    # Filter/sort apply to the DIRECT children only; paging + `total` reflect the filter.
    return facade.children(org_id, limit, offset, q, sort)


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
