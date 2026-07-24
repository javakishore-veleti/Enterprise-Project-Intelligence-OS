"""Use case: tracker-repository sync (trigger + governed two-level tracking log)."""
from __future__ import annotations

from ingestion_api.dtos.requests import (
    PlanSyncProjectRequest,
    RecordSyncBatchRequest,
    RecordSyncProjectsRequest,
    RepositorySyncRequest,
    UpdateSyncRunStatusRequest,
)
from ingestion_api.dtos.responses import SyncRunHandleResponse, SyncRunProgressResponse
from ingestion_api.interfaces.services import TrackerSyncService


class ManageTrackerSyncFacade:
    def __init__(self, service: TrackerSyncService) -> None:
        self._service = service

    def start(self, repo_id: str, request: RepositorySyncRequest) -> SyncRunHandleResponse:
        return self._service.start(repo_id, request)

    def progress(self, repo_id: str) -> SyncRunProgressResponse:
        return self._service.progress(repo_id)

    def progress_by_run(self, sync_run_id: str) -> SyncRunProgressResponse:
        return self._service.progress_by_run(sync_run_id)

    def record_run_projects(self, sync_run_id: str, request: RecordSyncProjectsRequest) -> None:
        self._service.record_run_projects(sync_run_id, request)

    def plan_project(self, sync_run_id: str, project_key: str, request: PlanSyncProjectRequest) -> None:
        self._service.plan_project(sync_run_id, project_key, request)

    def committed_batches(self, sync_run_id: str, project_key: str) -> list[int]:
        return self._service.committed_batches(sync_run_id, project_key)

    def record_batch(self, sync_run_id: str, request: RecordSyncBatchRequest) -> None:
        self._service.record_batch(sync_run_id, request)

    def finalize_run(self, sync_run_id: str, request: UpdateSyncRunStatusRequest) -> SyncRunProgressResponse:
        return self._service.finalize_run(sync_run_id, request)
