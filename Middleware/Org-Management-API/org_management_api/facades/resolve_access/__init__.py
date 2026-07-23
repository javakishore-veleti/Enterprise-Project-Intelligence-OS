"""Use case: effective-access resolution (visible / effective projects)."""
from __future__ import annotations

from org_management_api.dtos.common import VisibleProjectRecord
from org_management_api.dtos.responses import (
    EffectiveProjectsResponse,
    VisibleProjectResponse,
    VisibleProjectsResponse,
)
from org_management_api.interfaces.services import AccessService


def _project(rec: VisibleProjectRecord) -> VisibleProjectResponse:
    return VisibleProjectResponse(
        external_key=rec.external_key, name=rec.name, repo_id=rec.repo_id,
        org_id=rec.org_id, provider=rec.provider)


class ResolveAccessFacade:
    def __init__(self, service: AccessService) -> None:
        self._service = service

    def visible_projects(self, subject: str) -> VisibleProjectsResponse:
        records = self._service.visible_projects_for_subject(subject)
        return VisibleProjectsResponse(
            subject=subject, projects=[_project(r) for r in records])

    def effective_projects(self, org_id: str) -> EffectiveProjectsResponse:
        records = self._service.effective_projects_for_org(org_id)
        return EffectiveProjectsResponse(
            org_id=org_id, projects=[_project(r) for r in records])
