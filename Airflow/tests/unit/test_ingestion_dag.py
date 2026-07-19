"""Unit tests for the project dataset ingestion DAG.

Two layers, both hermetic (no network, no live Ingestion-API, no scheduler):

1. A DAG-parse test using ``airflow.models.DagBag`` asserting the ``dags/``
   folder imports with zero errors and exposes the expected DAG.
2. Direct tests of the pure task callables in ``project_dataset_ingest.tasks``
   against a *fake* HTTP client.
"""

from pathlib import Path

import pytest

from project_dataset_ingest import tasks

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeResponse:
    """Stand-in for a ``requests.Response``."""

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
    """Records calls and returns queued responses; mirrors the ``requests`` API."""

    def __init__(self, post_response=None, get_responses=None):
        self._post_response = post_response
        self._get_responses = list(get_responses or [])
        self.post_calls = []
        self.get_calls = []

    def post(self, url, json, timeout):  # noqa: A002 - matches requests signature
        self.post_calls.append({"url": url, "json": json, "timeout": timeout})
        return self._post_response

    def get(self, url, timeout):
        self.get_calls.append({"url": url, "timeout": timeout})
        # Return each queued response once, repeating the last one thereafter.
        if not self._get_responses:
            raise AssertionError("unexpected GET with no queued responses")
        if len(self._get_responses) == 1:
            return self._get_responses[0]
        return self._get_responses.pop(0)


# --------------------------------------------------------------------------- #
# 1. DAG parse test
# --------------------------------------------------------------------------- #
def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)

    assert dag_bag.import_errors == {}, f"DAG import errors: {dag_bag.import_errors}"
    assert "project_dataset_ingest" in dag_bag.dags


def test_dag_structure_and_schedule():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    # Read from the parsed in-memory dict (get_dag() would query the metadata DB).
    dag = dag_bag.dags["project_dataset_ingest"]

    assert dag is not None
    assert dag.schedule_interval is None  # manual / on-demand
    task_ids = set(dag.task_ids)
    assert task_ids == {
        "read_metadata",
        "check_disk_space",
        "start_ingestion",
        "poll_status",
        "finalize",
    }
    # Linear pipeline ordering.
    assert dag.get_task("check_disk_space").upstream_task_ids == {"read_metadata"}
    assert dag.get_task("start_ingestion").upstream_task_ids == {"check_disk_space"}
    assert dag.get_task("poll_status").upstream_task_ids == {"start_ingestion"}
    assert dag.get_task("finalize").upstream_task_ids == {"poll_status"}
    assert dag.default_args["retries"] == 3


# --------------------------------------------------------------------------- #
# 2. Task callable tests
# --------------------------------------------------------------------------- #
def test_get_base_url_default(monkeypatch):
    monkeypatch.delenv("INGESTION_API_BASE_URL", raising=False)
    assert tasks.get_base_url() == "http://localhost:8001"


def test_get_base_url_from_env_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("INGESTION_API_BASE_URL", "http://ingestion:8001/")
    assert tasks.get_base_url() == "http://ingestion:8001"


def test_read_metadata_valid():
    meta = tasks.read_metadata("ds-1", 500, 2, "airflow")
    assert meta == {
        "dataset_id": "ds-1",
        "batch_size": 500,
        "parallelism": 2,
        "requested_by": "airflow",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dataset_id": "", "batch_size": 1, "parallelism": 1, "requested_by": "x"},
        {"dataset_id": "d", "batch_size": 0, "parallelism": 1, "requested_by": "x"},
        {"dataset_id": "d", "batch_size": 1, "parallelism": 0, "requested_by": "x"},
        {"dataset_id": "d", "batch_size": 1, "parallelism": 1, "requested_by": ""},
    ],
)
def test_read_metadata_invalid(kwargs):
    with pytest.raises(ValueError):
        tasks.read_metadata(**kwargs)


def test_check_disk_space_ok():
    fake_usage = lambda path: type("U", (), {"total": 100, "used": 10, "free": 90})()
    result = tasks.check_disk_space(min_free_bytes=50, path="/data", usage_fn=fake_usage)
    assert result["free_bytes"] == 90
    assert result["min_free_bytes"] == 50


def test_check_disk_space_insufficient():
    fake_usage = lambda path: type("U", (), {"total": 100, "used": 95, "free": 5})()
    with pytest.raises(RuntimeError):
        tasks.check_disk_space(min_free_bytes=50, usage_fn=fake_usage)


def test_start_ingestion_posts_and_returns_run():
    http = FakeHttpClient(
        post_response=FakeResponse({"run_id": "run-123", "status": "PENDING"})
    )
    meta = {"dataset_id": "d", "batch_size": 1, "parallelism": 1, "requested_by": "x"}
    result = tasks.start_ingestion("http://api:8001", http, meta)

    assert result == {"run_id": "run-123", "status": "PENDING"}
    assert len(http.post_calls) == 1
    call = http.post_calls[0]
    assert call["url"] == "http://api:8001/api/v1/ingestion/runs"
    assert call["json"] == meta


def test_start_ingestion_missing_run_id_raises():
    http = FakeHttpClient(post_response=FakeResponse({"status": "PENDING"}))
    with pytest.raises(RuntimeError):
        tasks.start_ingestion("http://api:8001", http, {"dataset_id": "d"})


def test_start_ingestion_propagates_http_error():
    boom = RuntimeError("500 Server Error")
    http = FakeHttpClient(post_response=FakeResponse({}, status_code=500, error=boom))
    with pytest.raises(RuntimeError, match="500 Server Error"):
        tasks.start_ingestion("http://api:8001", http, {"dataset_id": "d"})


def test_poll_status_completes_after_running():
    http = FakeHttpClient(
        get_responses=[
            FakeResponse({"run_id": "r", "status": "PENDING"}),
            FakeResponse({"run_id": "r", "status": "RUNNING"}),
            FakeResponse({"run_id": "r", "status": "COMPLETED"}),
        ]
    )
    sleeps = []
    result = tasks.poll_status(
        "http://api:8001", http, "r", max_polls=5, sleep_fn=sleeps.append
    )
    assert result["status"] == "COMPLETED"
    assert len(http.get_calls) == 3
    assert len(sleeps) == 2  # slept between the three polls, not after the last


def test_poll_status_returns_failed_terminal():
    http = FakeHttpClient(get_responses=[FakeResponse({"run_id": "r", "status": "FAILED"})])
    result = tasks.poll_status("http://api:8001", http, "r", sleep_fn=lambda _: None)
    assert result["status"] == "FAILED"


def test_poll_status_times_out():
    http = FakeHttpClient(get_responses=[FakeResponse({"run_id": "r", "status": "RUNNING"})])
    with pytest.raises(TimeoutError):
        tasks.poll_status(
            "http://api:8001", http, "r", max_polls=3, sleep_fn=lambda _: None
        )


def test_poll_status_unknown_status_raises():
    http = FakeHttpClient(get_responses=[FakeResponse({"run_id": "r", "status": "WAT"})])
    with pytest.raises(RuntimeError):
        tasks.poll_status("http://api:8001", http, "r", sleep_fn=lambda _: None)


def test_finalize_completed_ok():
    summary = tasks.finalize({"run_id": "r", "status": "COMPLETED"})
    assert summary == {"run_id": "r", "status": "COMPLETED", "ok": True}


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "PAUSED"])
def test_finalize_non_success_raises(status):
    with pytest.raises(RuntimeError):
        tasks.finalize({"run_id": "r", "status": status})
