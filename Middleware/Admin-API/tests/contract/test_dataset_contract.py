"""Contract tests for the Admin dataset endpoints (fake ingestion gateway)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from admin_api.api.dependencies import provide_manage_dataset_facade
from admin_api.api.main import create_app
from admin_api.dtos.dataset import DatasetStatusResponse
from admin_api.facades.manage_dataset import ManageDatasetFacade
from admin_api.interfaces.daos import DatasetGateway

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _status(state):
    return DatasetStatusResponse(
        dataset_id="public-jira", title="The Public Jira Dataset", state=state,
        file_name="d.zip", source_url="http://x", expected_md5="abc", size_bytes=5813135238,
        downloaded_bytes=0, message="", updated_at=_NOW)


class _FakeGateway(DatasetGateway):
    def __init__(self):
        self.state = "NOT_DOWNLOADED"

    def get_status(self, dataset_id):
        return _status(self.state)

    def trigger_download(self, dataset_id):
        self.state = "DOWNLOADING"
        return _status(self.state)


def _client():
    app = create_app()
    facade = ManageDatasetFacade(_FakeGateway(), "public-jira")
    app.dependency_overrides[provide_manage_dataset_facade] = lambda: facade
    return TestClient(app)


def test_get_dataset_status() -> None:
    r = _client().get("/api/v1/admin/dataset/status")
    assert r.status_code == 200
    assert r.json()["dataset_id"] == "public-jira" and r.json()["state"] == "NOT_DOWNLOADED"


def test_download_triggers() -> None:
    c = _client()
    r = c.post("/api/v1/admin/dataset/download")
    assert r.status_code == 200 and r.json()["state"] == "DOWNLOADING"
