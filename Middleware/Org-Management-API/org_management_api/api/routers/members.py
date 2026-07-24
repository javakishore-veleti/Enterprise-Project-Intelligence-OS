"""User / membership / role endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from org_management_api.api.dependencies import provide_manage_members_facade
from org_management_api.dtos.requests import AddMemberRequest, CreateUserRequest
from org_management_api.dtos.responses import (
    MemberResponse,
    MembersResponse,
    RolesResponse,
    UserOrgsResponse,
    UserResponse,
)
from org_management_api.facades.manage_members import ManageMembersFacade

router = APIRouter(prefix="/api/v1", tags=["members"])

Facade = Depends(provide_manage_members_facade)


@router.post("/users", response_model=UserResponse,
             status_code=status.HTTP_201_CREATED, operation_id="createUser")
def create_user(request: CreateUserRequest, facade: ManageMembersFacade = Facade):
    return facade.create_user(request)


@router.post("/orgs/{org_id}/members", response_model=MemberResponse,
             status_code=status.HTTP_201_CREATED, operation_id="addOrganizationMember")
def add_member(org_id: str, request: AddMemberRequest, facade: ManageMembersFacade = Facade):
    return facade.add_member(org_id, request)


@router.get("/orgs/{org_id}/members", response_model=MembersResponse,
            operation_id="listOrganizationMembers")
def list_members(
    org_id: str,
    q: str | None = Query(default=None, description="Substring match on subject/display_name/email."),
    role: str | None = Query(default=None, description="Only members holding this direct role."),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: ManageMembersFacade = Facade,
):
    # Server-paged + filterable; each row carries direct + inherited roles.
    return facade.list_members_page(org_id, q, role, limit, offset)


@router.get("/roles", response_model=RolesResponse, operation_id="listRoles")
def list_roles(
    q: str | None = Query(
        default=None, description="Case-insensitive substring filter on role name."),
    limit: int = Query(default=25, ge=1, le=50),
    facade: ManageMembersFacade = Facade,
):
    # Distinct role names for a searchable role picker (never the full scroll list).
    return facade.list_roles(q, limit)


@router.get("/users/{subject}/orgs", response_model=UserOrgsResponse,
            operation_id="listUserOrganizations")
def list_user_orgs(subject: str, facade: ManageMembersFacade = Facade):
    return facade.list_orgs_for_user(subject)
