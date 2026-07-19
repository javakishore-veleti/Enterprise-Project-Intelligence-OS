"""Unit tests for the project dataset acquisition DAG.

Two layers, both hermetic (no network, no live Ingestion-API, no scheduler):

1. A DAG-parse test using ``airflow.models.DagBag``.
2. Direct tests of the pure task callables against a *fake* HTTP client.
"""

from pathlib import Path

import pytest

from project_dataset_acquire import tasks

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
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
    def __init__(self, post_responses=None, get_responses=None):
        self._post_responses = list(post_responses or [])
        self._get_responses = list(get_responses or [])
        self.post_calls = []
        self.get_calls = []

    def post(self, url, json, timeout):  # noqa: A002
        self.post_calls.append({"url": url, "json": json, "timeout": timeout})
        if not self._post_responses:
            raise AssertionError("unexpected POST with no queued responses")
        if len(self._post_responses) == 1:
            return self._post_responses[0]
        return self._post_responses.pop(0)

    def get(self, url, timeout):
        self.get_calls.append({"url": url, "timeout": timeout})
        if not self._get_responses:
            raise AssertionError("unexpected GET with no queued responses")
        if len(self._get_responses) == 1:
            return self._get_responses[0]
        return self._get_responses.pop(0)


# --------------------------------------------------------------------------- #
# 1. DAG parse tests
# --------------------------------------------------------------------------- #
def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert dag_bag.import_errors == {}, f"DAG import errors: {dag_bag.import_errors}"
    assert "project_dataset_acquire" in dag_bag.dags


def test_dag_structure_and_schedule():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    dag = dag_bag.dags["project_dataset_acquire"]

    assert dag is not None
    assert dag.schedule_interval is None  # on-demand
    assert set(dag.task_ids) == {
        "build_acquire_spec",
        "start_acquisition",
        "poll_acquisition",
        "verify_checksum",
        "extract_dataset",
        "finalize",
    }
    assert dag.get_task("start_acquisition").upstream_task_ids == {"build_acquire_spec"}
    assert dag.get_task("poll_acquisition").upstream_task_ids == {"start_acquisition"}
    assert dag.get_task("verify_checksum").upstream_task_ids == {"poll_acquisition"}
    assert dag.get_task("extract_dataset").upstream_task_ids == {"verify_checksum"}
    assert dag.get_task("finalize").upstream_task_ids == {"extract_dataset"}
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


def test_build_acquire_spec_valid():
    spec = tasks.build_acquire_spec("ds", "http://x/f.tgz", "a" * 64, "airflow")
    assert spec == {
        "dataset_id": "ds",
        "source_url": "http://x/f.tgz",
        "expected_sha256": "a" * 64,
        "requested_by": "airflow",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dataset_id": "", "source_url": "u", "expected_sha256": "s", "requested_by": "x"},
        {"dataset_id": "d", "source_url": "", "expected_sha256": "s", "requested_by": "x"},
        {"dataset_id": "d", "source_url": "u", "expected_sha256": "", "requested_by": "x"},
        {"dataset_id": "d", "source_url": "u", "expected_sha256": "s", "requested_by": ""},
    ],
)
def test_build_acquire_spec_invalid(kwargs):
    with pytest.raises(ValueError):
        tasks.build_acquire_spec(**kwargs)


def test_start_acquisition_posts_and_returns_id():
    http = FakeHttpClient(
        post_responses=[FakeResponse({"acquisition_id": "acq-1", "status": "PENDING"})]
    )
    spec = {"dataset_id": "d"}
    result = tasks.start_acquisition("http://api:8001", http, spec)

    assert result == {"acquisition_id": "acq-1", "status": "PENDING"}
    assert http.post_calls[0]["url"] == "http://api:8001/api/v1/ingestion/acquisitions"
    assert http.post_calls[0]["json"] == spec


def test_start_acquisition_missing_id_raises():
    http = FakeHttpClient(post_responses=[FakeResponse({"status": "PENDING"})])
    with pytest.raises(RuntimeError):
        tasks.start_acquisition("http://api:8001", http, {})


def test_start_acquisition_propagates_http_error():
    boom = RuntimeError("500 Server Error")
    http = FakeHttpClient(post_responses=[FakeResponse({}, 500, boom)])
    with pytest.raises(RuntimeError, match="500 Server Error"):
        tasks.start_acquisition("http://api:8001", http, {})


def test_poll_acquisition_completes():
    http = FakeHttpClient(
        get_responses=[
            FakeResponse({"acquisition_id": "a", "status": "DOWNLOADING"}),
            FakeResponse({"acquisition_id": "a", "status": "COMPLETED"}),
        ]
    )
    sleeps = []
    result = tasks.poll_acquisition(
        "http://api:8001", http, "a", max_polls=5, sleep_fn=sleeps.append
    )
    assert result["status"] == "COMPLETED"
    assert len(http.get_calls) == 2
    assert len(sleeps) == 1


def test_poll_acquisition_times_out():
    http = FakeHttpClient(
        get_responses=[FakeResponse({"acquisition_id": "a", "status": "DOWNLOADING"})]
    )
    with pytest.raises(TimeoutError):
        tasks.poll_acquisition("http://api:8001", http, "a", max_polls=2, sleep_fn=lambda _: None)


def test_poll_acquisition_unknown_status_raises():
    http = FakeHttpClient(get_responses=[FakeResponse({"status": "WAT"})])
    with pytest.raises(RuntimeError):
        tasks.poll_acquisition("http://api:8001", http, "a", sleep_fn=lambda _: None)


def test_verify_checksum_ok():
    http = FakeHttpClient(
        post_responses=[FakeResponse({"verified": True, "actual_sha256": "a" * 64})]
    )
    result = tasks.verify_checksum("http://api:8001", http, "a", "a" * 64)
    assert result["verified"] is True
    assert http.post_calls[0]["url"] == "http://api:8001/api/v1/ingestion/acquisitions/a/verify"
    assert http.post_calls[0]["json"] == {"expected_sha256": "a" * 64}


def test_verify_checksum_mismatch_raises():
    http = FakeHttpClient(
        post_responses=[FakeResponse({"verified": False, "actual_sha256": "b" * 64})]
    )
    with pytest.raises(RuntimeError):
        tasks.verify_checksum("http://api:8001", http, "a", "a" * 64)


def test_extract_dataset_ok():
    http = FakeHttpClient(post_responses=[FakeResponse({"extracted": True, "file_count": 12})])
    result = tasks.extract_dataset("http://api:8001", http, "a")
    assert result["file_count"] == 12
    assert http.post_calls[0]["url"] == "http://api:8001/api/v1/ingestion/acquisitions/a/extract"


def test_extract_dataset_incomplete_raises():
    http = FakeHttpClient(post_responses=[FakeResponse({"extracted": False})])
    with pytest.raises(RuntimeError):
        tasks.extract_dataset("http://api:8001", http, "a")


def test_finalize_summary():
    summary = tasks.finalize("acq-1", {"extracted": True, "file_count": 5})
    assert summary == {
        "acquisition_id": "acq-1",
        "extracted": True,
        "file_count": 5,
        "ok": True,
    }
