"""Contract tests for the dataset endpoints (fakes; no DB/Airflow)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from ingestion_api.api.dependencies import provide_manage_dataset_facade
from ingestion_api.api.main import create_app
from ingestion_api.dtos.common import DatasetState
from ingestion_api.dtos.responses import DatasetStatusResponse

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _status(state):
    return DatasetStatusResponse(
        dataset_id="public-jira", title="The Public Jira Dataset", state=state,
        file_name="d.zip", source_url="http://x", expected_md5="abc", size_bytes=100,
        downloaded_bytes=0, message="", updated_at=_NOW)


class _FakeFacade:
    def __init__(self):
        self.state = DatasetState.NOT_DOWNLOADED.value

    def get_status(self, dataset_id):
        return _status(self.state)

    def request_download(self, dataset_id):
        self.state = DatasetState.DOWNLOADING.value
        return _status(self.state)

    def update_status(self, dataset_id, request):
        self.state = request.state
        return _status(self.state)


def _client():
    app = create_app()
    app.dependency_overrides[provide_manage_dataset_facade] = lambda: _FakeFacade()
    return TestClient(app)


def test_get_status() -> None:
    r = _client().get("/api/v1/ingestion/datasets/public-jira")
    assert r.status_code == 200 and r.json()["state"] == "NOT_DOWNLOADED"


def test_acquire_marks_downloading() -> None:
    r = _client().post("/api/v1/ingestion/datasets/public-jira/acquire")
    assert r.status_code == 202 and r.json()["state"] == "DOWNLOADING"


def test_update_status() -> None:
    r = _client().put("/api/v1/ingestion/datasets/public-jira/status",
                      json={"state": "DOWNLOADED", "downloaded_bytes": 100})
    assert r.status_code == 200 and r.json()["state"] == "DOWNLOADED"
