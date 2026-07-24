"""Tracker-repository sync service.

Generates the ``sync_run_id``, inserts the run row, and triggers the Airflow
``tracker_repository_sync`` DAG passing that same id as the Airflow ``dag_run_id``
AND in the conf — so ``dag_run.run_id == sync_run_id`` and every tracking row
(run/project/batch) keys off it. Also governs the two-level tracking log the DAG
writes back through (projects/plan/batch/finalize) and serves aggregated progress.

``sync_run_id`` format: ``sync__<repo_id first 8>__<UTC compact timestamp>`` — human
readable + greppable, and identical across the DAG-run name, the "Sync now"
response, and the tracking PK.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ingestion_api.common.exceptions import NotFoundError
from ingestion_api.common.logging import get_logger
from ingestion_api.dtos.requests import (
    PlanSyncProjectRequest,
    RecordSyncBatchRequest,
    RecordSyncProjectsRequest,
    RepositorySyncRequest,
    UpdateSyncRunStatusRequest,
)
from ingestion_api.dtos.responses import (
    SyncRunHandleResponse,
    SyncRunProgressResponse,
)
from ingestion_api.interfaces.daos import SyncTrackingDao, TrackerSyncGateway
from ingestion_api.interfaces.services import TrackerSyncService

_logger = get_logger(__name__)


def build_sync_run_id(repo_id: str, now: datetime | None = None) -> str:
    """``sync__<repo-short>__<UTC yyyymmddHHMMSSffffff>`` — the one shared id."""
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%d%H%M%S%f")
    short = (repo_id or "repo").replace("-", "")[:8]
    return f"sync__{short}__{ts}"


class DefaultTrackerSyncService(TrackerSyncService):
    def __init__(self, tracking_dao: SyncTrackingDao, sync_gateway: TrackerSyncGateway) -> None:
        self._tracking = tracking_dao
        self._airflow = sync_gateway

    def start(self, repo_id: str, request: RepositorySyncRequest) -> SyncRunHandleResponse:
        sync_run_id = build_sync_run_id(repo_id)
        # Resolve the delta watermark: full -> None; explicit since -> that;
        # otherwise the last completed run's start (end-of-day delta base).
        if request.full:
            since = None
        elif request.since is not None:
            since = request.since
        else:
            since = self._tracking.last_completed_watermark(repo_id)

        self._tracking.insert_run(
            sync_run_id, repo_id, request.org_id, request.root_org_id,
            request.provider, since, request.requested_by)
        conf = {
            "sync_run_id": sync_run_id, "repo_id": repo_id,
            "org_id": request.org_id, "root_org_id": request.root_org_id,
            "provider": request.provider, "connection_config": request.connection_config,
            "since": since.isoformat() if since else None,
            "batch_size": request.batch_size, "requested_by": request.requested_by,
        }
        try:
            dag_run = self._airflow.trigger_sync(sync_run_id, conf)
        except Exception:
            self._tracking.finalize_run(sync_run_id, "FAILED", "Failed to trigger sync DAG.")
            raise
        _logger.info("tracker sync started", extra={"context": {
            "sync_run_id": sync_run_id, "repo_id": repo_id, "dag_run": dag_run,
            "since": since.isoformat() if since else None}})
        return SyncRunHandleResponse(
            sync_run_id=sync_run_id, repo_id=repo_id, provider=request.provider,
            status="RUNNING", since=since, dag_run=dag_run)

    def progress(self, repo_id: str) -> SyncRunProgressResponse:
        run = self._tracking.latest_run_for_repo(repo_id)
        if run is None:
            return SyncRunProgressResponse(sync_run_id=None, repo_id=repo_id, status="NOT_STARTED")
        return self._assemble(run)

    def progress_by_run(self, sync_run_id: str) -> SyncRunProgressResponse:
        run = self._tracking.get_run(sync_run_id)
        if run is None:
            raise NotFoundError(f"sync run '{sync_run_id}' not found")
        return self._assemble(run)

    def record_run_projects(self, sync_run_id: str, request: RecordSyncProjectsRequest) -> None:
        self._require_run(sync_run_id)
        self._tracking.set_run_projects(
            sync_run_id, request.projects_intended, request.projects_considered)

    def plan_project(self, sync_run_id: str, project_key: str, request: PlanSyncProjectRequest) -> None:
        self._require_run(sync_run_id)
        self._tracking.upsert_project_plan(
            sync_run_id, project_key, request.issues_intended, request.batches_total)

    def committed_batches(self, sync_run_id: str, project_key: str) -> list[int]:
        return sorted(self._tracking.committed_batch_numbers(sync_run_id, project_key))

    def record_batch(self, sync_run_id: str, request: RecordSyncBatchRequest) -> None:
        self._require_run(sync_run_id)
        self._tracking.commit_batch(
            sync_run_id, request.project_key, request.batch_no,
            request.source_offset, request.record_count)

    def finalize_run(self, sync_run_id: str, request: UpdateSyncRunStatusRequest) -> SyncRunProgressResponse:
        run = self._tracking.finalize_run(sync_run_id, request.status, request.message)
        if run is None:
            raise NotFoundError(f"sync run '{sync_run_id}' not found")
        return self._assemble(run)

    # --- helpers ---
    def _require_run(self, sync_run_id: str) -> dict:
        run = self._tracking.get_run(sync_run_id)
        if run is None:
            raise NotFoundError(f"sync run '{sync_run_id}' not found")
        return run

    def _assemble(self, run: dict) -> SyncRunProgressResponse:
        sync_run_id = run["sync_run_id"]
        return SyncRunProgressResponse(
            sync_run_id=sync_run_id, repo_id=run["repo_id"], org_id=run["org_id"],
            root_org_id=run["root_org_id"], provider=run["provider"], status=run["status"],
            since=run["since"], projects_intended=run["projects_intended"],
            projects_considered=run["projects_considered"], projects_total=run["projects_total"],
            issues_total=run["issues_total"], started_at=run["started_at"],
            completed_at=run["completed_at"],
            projects=self._tracking.project_progress(sync_run_id),
            recent_batches=self._tracking.recent_batches(sync_run_id, 25))
