"""Unit tests for the dataset service against fakes (no DB, no Airflow)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingestion_api.common.exceptions import DependencyUnavailableError, NotFoundError
from ingestion_api.dtos.common import DatasetState
from ingestion_api.dtos.requests import UpdateDatasetStatusRequest
from ingestion_api.dtos.responses import DatasetStatusResponse
from ingestion_api.interfaces.daos import DatasetAcquisitionGateway, DatasetsDao
from ingestion_api.services.datasets import DefaultDatasetService

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _status(state: str, downloaded_bytes: int = 0) -> DatasetStatusResponse:
    return DatasetStatusResponse(
        dataset_id="public-jira", title="The Public Jira Dataset", state=state,
        file_name="d.zip", source_url="http://x", expected_md5="abc", size_bytes=100,
        downloaded_bytes=downloaded_bytes, message="", updated_at=_NOW,
    )


class FakeDao(DatasetsDao):
    def __init__(self, state=DatasetState.NOT_DOWNLOADED.value):
        self.row = _status(state)
        self.updates = []

    def get(self, dataset_id):
        return self.row if dataset_id == "public-jira" else None

    def update_status(self, dataset_id, state, **kw):
        self.updates.append((state, kw))
        self.row = self.row.model_copy(update={"state": state, **{
            k: v for k, v in kw.items() if k in ("downloaded_bytes", "message") and v is not None
        }})
        return self.row


class FakeGateway(DatasetAcquisitionGateway):
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def trigger_acquire(self, dataset_id):
        self.calls.append(dataset_id)
        if self.fail:
            raise DependencyUnavailableError("airflow down")
        return "run-123"


def test_get_status_missing_raises() -> None:
    svc = DefaultDatasetService(FakeDao(), FakeGateway())
    with pytest.raises(NotFoundError):
        svc.get_status("nope")


def test_request_download_triggers_and_marks_downloading() -> None:
    dao, gw = FakeDao(), FakeGateway()
    result = DefaultDatasetService(dao, gw).request_download("public-jira")
    assert gw.calls == ["public-jira"]
    assert result.state == DatasetState.DOWNLOADING.value


def test_request_download_idempotent_when_already_downloaded() -> None:
    dao, gw = FakeDao(DatasetState.DOWNLOADED.value), FakeGateway()
    result = DefaultDatasetService(dao, gw).request_download("public-jira")
    assert gw.calls == []  # no re-trigger
    assert result.state == DatasetState.DOWNLOADED.value


def test_request_download_idempotent_when_in_progress() -> None:
    dao, gw = FakeDao(DatasetState.DOWNLOADING.value), FakeGateway()
    DefaultDatasetService(dao, gw).request_download("public-jira")
    assert gw.calls == []


def test_request_download_propagates_airflow_unavailable() -> None:
    dao, gw = FakeDao(), FakeGateway(fail=True)
    with pytest.raises(DependencyUnavailableError):
        DefaultDatasetService(dao, gw).request_download("public-jira")
    # state not advanced when the trigger fails
    assert dao.row.state == DatasetState.NOT_DOWNLOADED.value


def test_update_status_downloaded_sets_flag() -> None:
    dao = FakeDao(DatasetState.DOWNLOADING.value)
    svc = DefaultDatasetService(dao, FakeGateway())
    svc.update_status("public-jira", UpdateDatasetStatusRequest(
        state=DatasetState.DOWNLOADED.value, downloaded_bytes=100, downloaded_path="/data/d.zip"))
    state, kw = dao.updates[-1]
    assert state == "DOWNLOADED" and kw["set_downloaded_at"] is True
