"""Project query endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from projects_api.api.dependencies import (
    provide_get_project_facade,
    provide_get_project_metrics_facade,
    provide_search_projects_facade,
)
from projects_api.dtos.requests import SearchProjectsRequest
from projects_api.dtos.responses import (
    ProjectMetricsResponse,
    ProjectResponse,
    ProjectSearchResponse,
)
from projects_api.facades.get_project import GetProjectFacade
from projects_api.facades.get_project_metrics import GetProjectMetricsFacade
from projects_api.facades.search_projects import SearchProjectsFacade

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=ProjectSearchResponse, operation_id="searchProjects")
def search_projects(
    query: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: SearchProjectsFacade = Depends(provide_search_projects_facade),
) -> ProjectSearchResponse:
    return facade.execute(SearchProjectsRequest(query=query, limit=limit, offset=offset))


@router.get("/{project_key}", response_model=ProjectResponse, operation_id="getProject")
def get_project(
    project_key: str,
    facade: GetProjectFacade = Depends(provide_get_project_facade),
) -> ProjectResponse:
    return facade.execute(project_key)


@router.get(
    "/{project_key}/metrics",
    response_model=ProjectMetricsResponse,
    operation_id="getProjectMetrics",
)
def get_project_metrics(
    project_key: str,
    facade: GetProjectMetricsFacade = Depends(provide_get_project_metrics_facade),
) -> ProjectMetricsResponse:
    return facade.execute(project_key)
