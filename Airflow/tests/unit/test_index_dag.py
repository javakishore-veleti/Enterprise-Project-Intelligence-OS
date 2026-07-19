"""Unit tests for the project dataset indexing DAG (hermetic)."""

from pathlib import Path

import pytest

from project_dataset_index import tasks

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"


class FakeResponse:
    def __init__(self, payload, status_code=200, error=None):
        self._payload = payload
        self.status_code = status_code
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self, post_response=None, get_responses=None):
        self._post_response = post_response
        self._get_responses = list(get_responses or [])
        self.post_calls = []
        self.get_calls = []

    def post(self, url, json, timeout):  # noqa: A002
        self.post_calls.append({"url": url, "json": json, "timeout": timeout})
        return self._post_response

    def get(self, url, timeout):
        self.get_calls.append({"url": url, "timeout": timeout})
        if not self._get_responses:
            raise AssertionError("unexpected GET with no queued responses")
        if len(self._get_responses) == 1:
            return self._get_responses[0]
        return self._get_responses.pop(0)


def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert dag_bag.import_errors == {}, f"DAG import errors: {dag_bag.import_errors}"
    assert "project_dataset_index" in dag_bag.dags


def test_dag_structure_and_schedule():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    dag = dag_bag.dags["project_dataset_index"]

    assert dag.schedule_interval is None
    assert set(dag.task_ids) == {
        "build_index_request",
        "start_indexing",
        "poll_indexing",
        "finalize",
    }
    assert dag.get_task("start_indexing").upstream_task_ids == {"build_index_request"}
    assert dag.get_task("poll_indexing").upstream_task_ids == {"start_indexing"}
    assert dag.get_task("finalize").upstream_task_ids == {"poll_indexing"}
    assert dag.default_args["retries"] == 3


def test_get_base_url_default(monkeypatch):
    monkeypatch.delenv("INGESTION_API_BASE_URL", raising=False)
    assert tasks.get_base_url() == "http://localhost:8001"


def test_build_index_request_valid():
    req = tasks.build_index_request("ds", ["issues"], "airflow", concurrently=False)
    assert req == {
        "dataset_id": "ds",
        "targets": ["issues"],
        "requested_by": "airflow",
        "concurrently": False,
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dataset_id": "", "targets": ["t"], "requested_by": "x"},
        {"dataset_id": "d", "targets": [], "requested_by": "x"},
        {"dataset_id": "d", "targets": ["t"], "requested_by": ""},
    ],
)
def test_build_index_request_invalid(kwargs):
    with pytest.raises(ValueError):
        tasks.build_index_request(**kwargs)


def test_start_indexing_posts_and_returns_id():
    http = FakeHttpClient(
        post_response=FakeResponse({"index_job_id": "ix-1", "status": "PENDING"})
    )
    req = {"dataset_id": "d", "targets": ["issues"], "requested_by": "x", "concurrently": True}
    result = tasks.start_indexing("http://api:8001", http, req)
    assert result == {"index_job_id": "ix-1", "status": "PENDING"}
    assert http.post_calls[0]["url"] == "http://api:8001/api/v1/ingestion/indexes"


def test_start_indexing_missing_id_raises():
    http = FakeHttpClient(post_response=FakeResponse({"status": "PENDING"}))
    with pytest.raises(RuntimeError):
        tasks.start_indexing("http://api:8001", http, {})


def test_poll_indexing_completes():
    http = FakeHttpClient(
        get_responses=[
            FakeResponse({"index_job_id": "ix", "status": "RUNNING"}),
            FakeResponse({"index_job_id": "ix", "status": "COMPLETED", "indexes_created": 7}),
        ]
    )
    result = tasks.poll_indexing("http://api:8001", http, "ix", sleep_fn=lambda _: None)
    assert result["status"] == "COMPLETED"


def test_poll_indexing_unknown_status_raises():
    http = FakeHttpClient(get_responses=[FakeResponse({"status": "WAT"})])
    with pytest.raises(RuntimeError):
        tasks.poll_indexing("http://api:8001", http, "ix", sleep_fn=lambda _: None)


def test_finalize_completed_ok():
    summary = tasks.finalize({"index_job_id": "ix", "status": "COMPLETED", "indexes_created": 7})
    assert summary == {
        "index_job_id": "ix",
        "status": "COMPLETED",
        "indexes_created": 7,
        "ok": True,
    }


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED"])
def test_finalize_non_success_raises(status):
    with pytest.raises(RuntimeError):
        tasks.finalize({"index_job_id": "ix", "status": status})
