"""Project query endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from projects_api.api.dependencies import (
    provide_compute_metrics_facade,
    provide_get_project_facade,
    provide_get_project_metrics_facade,
    provide_search_projects_facade,
)
from projects_api.dtos.requests import SearchProjectsRequest
from projects_api.dtos.responses import (
    ProjectMetricsHistoryResponse,
    ProjectMetricsResponse,
    ProjectResponse,
    ProjectSearchResponse,
)
from projects_api.facades.compute_metrics import ComputeMetricsFacade
from projects_api.facades.get_project import GetProjectFacade
from projects_api.facades.get_project_metrics import GetProjectMetricsFacade
from projects_api.facades.search_projects import SearchProjectsFacade

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("/metrics/compute-all", operation_id="computeAllProjectMetrics")
def compute_all_metrics(
    limit: int = Query(default=1000, ge=1, le=5000),
    facade: ComputeMetricsFacade = Depends(provide_compute_metrics_facade),
) -> dict:
    """Recompute metrics for every project from ingested evidence (batch)."""
    computed = facade.compute_all(limit)
    return {"computed": computed, "count": len(computed)}


@router.post("/{project_key}/metrics/compute", response_model=ProjectMetricsResponse,
             operation_id="computeProjectMetrics")
def compute_project_metrics(
    project_key: str,
    facade: ComputeMetricsFacade = Depends(provide_compute_metrics_facade),
) -> ProjectMetricsResponse:
    """Recompute a single project's metrics from ingested evidence."""
    return facade.compute(project_key)


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


@router.get(
    "/{project_key}/metrics/history",
    response_model=ProjectMetricsHistoryResponse,
    operation_id="getProjectMetricsHistory",
)
def get_project_metrics_history(
    project_key: str,
    limit: int = Query(default=50, ge=1, le=500),
    facade: GetProjectMetricsFacade = Depends(provide_get_project_metrics_facade),
) -> ProjectMetricsHistoryResponse:
    return ProjectMetricsHistoryResponse(
        project_key=project_key, history=facade.history(project_key, limit))
