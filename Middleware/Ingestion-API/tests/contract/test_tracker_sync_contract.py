"""Contract tests for the tracker-sync endpoints (fakes; no DB/Airflow)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from ingestion_api.api.dependencies import provide_manage_tracker_sync_facade
from ingestion_api.api.main import create_app
from ingestion_api.dtos.responses import (
    SyncProjectProgress,
    SyncRunHandleResponse,
    SyncRunProgressResponse,
)

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


class _FakeFacade:
    def __init__(self):
        self.batches = []
        self.finalized = []
        self.projects_recorded = None

    def start(self, repo_id, request):
        return SyncRunHandleResponse(
            sync_run_id=f"sync__{repo_id[:8]}__20260701", repo_id=repo_id,
            provider=request.provider, status="RUNNING", since=request.since,
            dag_run="dag:sync__x")

    def progress(self, repo_id):
        return SyncRunProgressResponse(
            sync_run_id="sync__x", repo_id=repo_id, status="RUNNING",
            projects=[SyncProjectProgress(project_key="Sakai", status="IN_PROGRESS")])

    def progress_by_run(self, sync_run_id):
        return SyncRunProgressResponse(sync_run_id=sync_run_id, repo_id="repo-1", status="COMPLETED")

    def record_run_projects(self, sync_run_id, request):
        self.projects_recorded = (sync_run_id, request.projects_intended)

    def plan_project(self, sync_run_id, project_key, request):
        pass

    def committed_batches(self, sync_run_id, project_key):
        return [0, 1]

    def record_batch(self, sync_run_id, request):
        self.batches.append((sync_run_id, request.project_key, request.batch_no))

    def finalize_run(self, sync_run_id, request):
        self.finalized.append((sync_run_id, request.status))
        return SyncRunProgressResponse(sync_run_id=sync_run_id, repo_id="repo-1", status="COMPLETED")


def _client():
    app = create_app()
    facade = _FakeFacade()
    app.dependency_overrides[provide_manage_tracker_sync_facade] = lambda: facade
    return TestClient(app), facade


def test_start_repository_sync():
    client, _ = _client()
    r = client.post("/api/v1/ingestion/repositories/repo-123/sync",
                    json={"org_id": "org-1", "root_org_id": "root-1", "provider": "fake"})
    assert r.status_code == 202
    body = r.json()
    assert body["sync_run_id"].startswith("sync__") and body["status"] == "RUNNING"


def test_get_repository_sync_progress():
    client, _ = _client()
    r = client.get("/api/v1/ingestion/repositories/repo-123/sync")
    assert r.status_code == 200
    assert r.json()["projects"][0]["project_key"] == "Sakai"


def test_get_sync_run_progress():
    client, _ = _client()
    r = client.get("/api/v1/ingestion/sync-runs/sync__abc")
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"


def test_record_run_projects_callback():
    client, facade = _client()
    r = client.post("/api/v1/ingestion/sync-runs/sync__x/projects",
                    json={"projects_intended": ["Sakai", "Spring"], "projects_considered": 2})
    assert r.status_code == 204
    assert facade.projects_recorded == ("sync__x", ["Sakai", "Spring"])


def test_committed_batches_callback():
    client, _ = _client()
    r = client.get("/api/v1/ingestion/sync-runs/sync__x/projects/Sakai/committed-batches")
    assert r.status_code == 200 and r.json()["batch_numbers"] == [0, 1]


def test_record_batch_callback():
    client, facade = _client()
    r = client.post("/api/v1/ingestion/sync-runs/sync__x/batches",
                    json={"project_key": "Sakai", "batch_no": 2, "source_offset": 4, "record_count": 2})
    assert r.status_code == 200
    assert facade.batches == [("sync__x", "Sakai", 2)]


def test_finalize_sync_run_callback():
    client, facade = _client()
    r = client.put("/api/v1/ingestion/sync-runs/sync__x/status", json={"status": "COMPLETED"})
    assert r.status_code == 200
    assert facade.finalized == [("sync__x", "COMPLETED")]
