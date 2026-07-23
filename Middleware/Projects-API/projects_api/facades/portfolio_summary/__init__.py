"""Use case: rank the portfolio by risk and return the top N.

Owns the per-user scoping decision: if a ``user_key`` is supplied AND it has
project assignments, the ranking/totals/bands are narrowed to that user's
projects; otherwise it falls back to the whole portfolio (anonymous / unknown
user). The narrowing itself happens in the DB (see the DAO ``$match``).
"""
from __future__ import annotations

from datetime import date

from projects_api.common.utilities import narrow_with_org_scope
from projects_api.dtos.common import OrgScope
from projects_api.dtos.responses import PortfolioSummaryResponse
from projects_api.interfaces.daos import ProjectAssignmentsDao
from projects_api.interfaces.facades import PortfolioSummaryUseCase
from projects_api.interfaces.services import PortfolioSummaryService


class PortfolioSummaryFacade(PortfolioSummaryUseCase):
    def __init__(
        self,
        service: PortfolioSummaryService,
        assignments: ProjectAssignmentsDao | None = None,
    ) -> None:
        self._service = service
        self._assignments = assignments

    def execute(
        self,
        top: int,
        user_key: str | None = None,
        as_of: date | None = None,
        org_scope: OrgScope | None = None,
    ) -> PortfolioSummaryResponse:
        project_keys: list[str] | None = None
        scoped = False
        if user_key and self._assignments is not None:
            assigned = self._assignments.project_keys_for(user_key)
            if assigned:
                # Known user with assignments -> scope to just those projects.
                project_keys = assigned
                scoped = True
        # Phase-2: AND the org tenancy scope over the legacy scope (no-op when
        # absent). A present org scope always produces a concrete key list, so
        # ``scoped`` reflects that the ranking/totals are narrowed.
        if org_scope is not None:
            project_keys = narrow_with_org_scope(project_keys, org_scope)
            scoped = True
        return self._service.summarize(
            top, project_keys=project_keys, user_key=user_key, scoped=scoped, as_of=as_of
        )
