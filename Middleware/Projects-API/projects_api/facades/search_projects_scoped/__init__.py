"""Use case: scale-hardened, risk-ranked, paginated project search.

Owns the same per-user scoping decision as the portfolio summary: if the
request carries a ``scope`` (user key) that has project assignments, the search
is narrowed to that user's projects (in the DB); otherwise it covers all
projects. The narrowing itself happens in the DAO ``$match``.
"""
from __future__ import annotations

from projects_api.dtos.requests import ScopedProjectSearchRequest
from projects_api.dtos.responses import ScopedProjectSearchResponse
from projects_api.interfaces.daos import ProjectAssignmentsDao
from projects_api.interfaces.facades import SearchProjectsScopedUseCase
from projects_api.interfaces.services import ProjectQueryService


class SearchProjectsScopedFacade(SearchProjectsScopedUseCase):
    def __init__(
        self,
        service: ProjectQueryService,
        assignments: ProjectAssignmentsDao | None = None,
    ) -> None:
        self._service = service
        self._assignments = assignments

    def execute(self, request: ScopedProjectSearchRequest) -> ScopedProjectSearchResponse:
        project_keys: list[str] | None = None
        if request.scope and self._assignments is not None:
            assigned = self._assignments.project_keys_for(request.scope)
            if assigned:
                # Known user with assignments -> scope to just those projects.
                project_keys = assigned
        return self._service.search_scoped(request, project_keys)
