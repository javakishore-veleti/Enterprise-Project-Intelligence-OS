"""Tracker-repository sync endpoints (trigger + progress + DAG tracking callbacks).

Public "Sync now" + progress polling are for the UI; the ``sync-runs/...`` POST/PUT
callbacks are the governed boundary the ``tracker_repository_sync`` DAG writes its
two-level tracking log through (run / project / batch). Every path keys off the
``sync_run_id`` — which equals the Airflow ``dag_run_id`` of the run.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from ingestion_api.api.dependencies import provide_manage_tracker_sync_facade
from ingestion_api.dtos.requests import (
    PlanSyncProjectRequest,
    RecordSyncBatchRequest,
    RecordSyncProjectsRequest,
    RepositorySyncRequest,
    UpdateSyncRunStatusRequest,
)
from ingestion_api.dtos.responses import SyncRunHandleResponse, SyncRunProgressResponse
from ingestion_api.facades.manage_tracker_sync import ManageTrackerSyncFacade

router = APIRouter(tags=["tracker-sync"])

Facade = Depends(provide_manage_tracker_sync_facade)


# --- UI: trigger + poll ------------------------------------------------------ #
@router.post("/api/v1/ingestion/repositories/{repo_id}/sync",
             response_model=SyncRunHandleResponse,
             status_code=status.HTTP_202_ACCEPTED, operation_id="startRepositorySync")
def start_repository_sync(repo_id: str, request: RepositorySyncRequest,
                          facade: ManageTrackerSyncFacade = Facade):
    """"Sync now" — trigger the sync DAG; the returned sync_run_id is the DAG-run id."""
    return facade.start(repo_id, request)


@router.get("/api/v1/ingestion/repositories/{repo_id}/sync",
            response_model=SyncRunProgressResponse, operation_id="getRepositorySyncProgress")
def get_repository_sync_progress(repo_id: str, facade: ManageTrackerSyncFacade = Facade):
    """Latest sync-run progress for a repo (run + per-project + recent batches)."""
    return facade.progress(repo_id)


@router.get("/api/v1/ingestion/sync-runs/{sync_run_id}",
            response_model=SyncRunProgressResponse, operation_id="getSyncRunProgress")
def get_sync_run_progress(sync_run_id: str, facade: ManageTrackerSyncFacade = Facade):
    """Full progress of a specific sync run (run + per-project + per-batch)."""
    return facade.progress_by_run(sync_run_id)


# --- Governed DAG callbacks (two-level tracking log) ------------------------- #
@router.post("/api/v1/ingestion/sync-runs/{sync_run_id}/projects",
             status_code=status.HTTP_204_NO_CONTENT, operation_id="recordSyncRunProjects")
def record_sync_run_projects(sync_run_id: str, request: RecordSyncProjectsRequest,
                             facade: ManageTrackerSyncFacade = Facade):
    facade.record_run_projects(sync_run_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/v1/ingestion/sync-runs/{sync_run_id}/projects/{project_key}/plan",
             status_code=status.HTTP_204_NO_CONTENT, operation_id="planSyncProject")
def plan_sync_project(sync_run_id: str, project_key: str, request: PlanSyncProjectRequest,
                      facade: ManageTrackerSyncFacade = Facade):
    facade.plan_project(sync_run_id, project_key, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/v1/ingestion/sync-runs/{sync_run_id}/projects/{project_key}/committed-batches",
            operation_id="getSyncCommittedBatches")
def sync_committed_batches(sync_run_id: str, project_key: str,
                           facade: ManageTrackerSyncFacade = Facade):
    """Batch numbers already committed for (run, project) — the DAG skips these to resume."""
    return {"sync_run_id": sync_run_id, "project_key": project_key,
            "batch_numbers": facade.committed_batches(sync_run_id, project_key)}


@router.post("/api/v1/ingestion/sync-runs/{sync_run_id}/batches",
             response_model=SyncRunProgressResponse, operation_id="recordSyncBatch")
def record_sync_batch(sync_run_id: str, request: RecordSyncBatchRequest,
                      facade: ManageTrackerSyncFacade = Facade):
    """Commit a batch checkpoint (atomic project-counter bump); return run progress."""
    facade.record_batch(sync_run_id, request)
    return facade.progress_by_run(sync_run_id)


@router.put("/api/v1/ingestion/sync-runs/{sync_run_id}/status",
            response_model=SyncRunProgressResponse, operation_id="finalizeSyncRun")
def finalize_sync_run(sync_run_id: str, request: UpdateSyncRunStatusRequest,
                      facade: ManageTrackerSyncFacade = Facade):
    """Reconcile the run status from project rollups (posted by the DAG ``finalize``)."""
    return facade.finalize_run(sync_run_id, request)
