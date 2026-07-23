"""User / membership / role endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from org_management_api.api.dependencies import provide_manage_members_facade
from org_management_api.dtos.requests import AddMemberRequest, CreateUserRequest
from org_management_api.dtos.responses import (
    MemberResponse,
    MembersResponse,
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
def list_members(org_id: str, facade: ManageMembersFacade = Facade):
    return facade.list_members(org_id)


@router.get("/users/{subject}/orgs", response_model=UserOrgsResponse,
            operation_id="listUserOrganizations")
def list_user_orgs(subject: str, facade: ManageMembersFacade = Facade):
    return facade.list_orgs_for_user(subject)
