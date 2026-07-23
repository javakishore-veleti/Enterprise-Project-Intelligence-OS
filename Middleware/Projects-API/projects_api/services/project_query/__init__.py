"""Project query service — search and fetch projects from the evidence store."""
from __future__ import annotations

from projects_api.common.configuration import Settings
from projects_api.common.exceptions import NotFoundError
from projects_api.common.utilities import clamp_page_size
from projects_api.dtos.common import PageMeta, PortfolioScoredRow, ProjectSearchScoredRow
from projects_api.dtos.requests import ScopedProjectSearchRequest, SearchProjectsRequest
from projects_api.dtos.responses import (
    ProjectResponse,
    ProjectSearchItem,
    ProjectSearchResponse,
    ScopedProjectSearchResponse,
)
from projects_api.interfaces.daos import ProjectsDao
from projects_api.interfaces.services import ProjectQueryService
from projects_api.services.portfolio_summary import risk_band, risk_score

# Hard cap on the page size for the scale-hardened search (task contract).
_SEARCH_LIMIT_CAP = 100


def _scored_item(row: ProjectSearchScoredRow) -> tuple[ProjectSearchItem, float | None]:
    """Build the response item + its sort score, reusing the portfolio ranking's
    composite risk_score/band (unscored rows -> null score/band, ranked last)."""
    score: float | None = None
    band: str | None = None
    if row.has_metrics:
        score = risk_score(PortfolioScoredRow(
            project_key=row.project_key,
            name=row.name,
            issue_count=row.issue_count,
            open_issue_count=row.open_issue_count,
            blocker_count=row.blocker_count,
            reopen_rate=row.reopen_rate,
            issue_aging_days=row.issue_aging_days,
            critical_defect_ratio=row.critical_defect_ratio,
        ))
        band = risk_band(score)
    return (
        ProjectSearchItem(
            project_key=row.project_key,
            name=row.name,
            risk_score=score,
            risk_band=band,
            open_issue_count=row.open_issue_count,
        ),
        score,
    )


class DefaultProjectQueryService(ProjectQueryService):
    def __init__(self, projects_dao: ProjectsDao, settings: Settings) -> None:
        self._dao = projects_dao
        self._settings = settings

    def search(self, request: SearchProjectsRequest) -> ProjectSearchResponse:
        limit = clamp_page_size(
            request.limit, self._settings.default_page_size, self._settings.max_page_size
        )
        items, total = self._dao.search(request.query, limit, request.offset)
        return ProjectSearchResponse(
            items=items,
            page=PageMeta(total=total, limit=limit, offset=request.offset),
        )

    def search_scoped(
        self, request: ScopedProjectSearchRequest, project_keys: list[str] | None
    ) -> ScopedProjectSearchResponse:
        # Clamp the page size to the documented ceiling (defensive; the router
        # already bounds it).
        limit = min(max(request.limit, 1), _SEARCH_LIMIT_CAP)
        offset = max(request.offset, 0)

        rows = self._dao.search_scored(request.query, project_keys)
        scored = [_scored_item(r) for r in rows]
        # risk_score desc (nulls last), then project_key asc — deterministic.
        scored.sort(key=lambda pair: (
            0 if pair[1] is not None else 1,
            -(pair[1] or 0.0),
            pair[0].project_key,
        ))
        total = len(scored)
        page = [item for item, _ in scored[offset:offset + limit]]
        return ScopedProjectSearchResponse(
            total=total, returned=len(page), offset=offset, limit=limit, items=page
        )

    def get(self, project_key: str) -> ProjectResponse:
        project = self._dao.get(project_key)
        if project is None:
            raise NotFoundError(f"project '{project_key}' not found")
        return project
