"""Effective-access resolution endpoints (the key tenancy query surface).

`visible-projects` for a user = union of tracker projects visible to any org the
user is a member of, per each repository's visibility_scope + grants.
`effective-projects` resolves the same from a single org context.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from org_management_api.api.dependencies import provide_resolve_access_facade
from org_management_api.dtos.responses import (
    EffectiveProjectsResponse,
    VisibleProjectsResponse,
)
from org_management_api.facades.resolve_access import ResolveAccessFacade

router = APIRouter(prefix="/api/v1", tags=["access"])

Facade = Depends(provide_resolve_access_facade)


@router.get("/users/{subject}/visible-projects", response_model=VisibleProjectsResponse,
            operation_id="getUserVisibleProjects")
def user_visible_projects(
    subject: str,
    q: str | None = Query(
        default=None, description="Substring filter on project external_key / name."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: ResolveAccessFacade = Facade,
):
    # Server-paged + searchable — a subject's visible-projects set can be huge.
    return facade.visible_projects(subject, q, limit, offset)


@router.get("/orgs/{org_id}/effective-projects", response_model=EffectiveProjectsResponse,
            operation_id="getOrganizationEffectiveProjects")
def org_effective_projects(
    org_id: str,
    q: str | None = Query(
        default=None, description="Substring filter on project external_key / name."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: ResolveAccessFacade = Facade,
):
    return facade.effective_projects(org_id, q, limit, offset)
