"""Unit tests for the project dataset validation DAG (hermetic)."""

from pathlib import Path

import pytest

from project_dataset_validate import tasks

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
    assert "project_dataset_validate" in dag_bag.dags


def test_dag_structure_and_schedule():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    dag = dag_bag.dags["project_dataset_validate"]

    assert dag.schedule_interval is None
    assert set(dag.task_ids) == {
        "build_validation_request",
        "start_validation",
        "poll_validation",
        "evaluate_validation",
    }
    assert dag.get_task("start_validation").upstream_task_ids == {"build_validation_request"}
    assert dag.get_task("poll_validation").upstream_task_ids == {"start_validation"}
    assert dag.get_task("evaluate_validation").upstream_task_ids == {"poll_validation"}
    assert dag.default_args["retries"] == 3


def test_get_base_url_default(monkeypatch):
    monkeypatch.delenv("INGESTION_API_BASE_URL", raising=False)
    assert tasks.get_base_url() == "http://localhost:8001"


def test_build_validation_request_valid_with_run_id():
    req = tasks.build_validation_request("ds", "airflow", max_invalid=5, run_id="r-1")
    assert req == {
        "dataset_id": "ds",
        "requested_by": "airflow",
        "max_invalid": 5,
        "run_id": "r-1",
    }


def test_build_validation_request_omits_run_id_when_absent():
    req = tasks.build_validation_request("ds", "airflow")
    assert "run_id" not in req
    assert req["max_invalid"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dataset_id": "", "requested_by": "x"},
        {"dataset_id": "d", "requested_by": ""},
        {"dataset_id": "d", "requested_by": "x", "max_invalid": -1},
    ],
)
def test_build_validation_request_invalid(kwargs):
    with pytest.raises(ValueError):
        tasks.build_validation_request(**kwargs)


def test_start_validation_posts_and_returns_id():
    http = FakeHttpClient(
        post_response=FakeResponse({"validation_id": "v-1", "status": "PENDING"})
    )
    req = {"dataset_id": "d", "requested_by": "x", "max_invalid": 0}
    result = tasks.start_validation("http://api:8001", http, req)
    assert result == {"validation_id": "v-1", "status": "PENDING"}
    assert http.post_calls[0]["url"] == "http://api:8001/api/v1/ingestion/validations"


def test_start_validation_missing_id_raises():
    http = FakeHttpClient(post_response=FakeResponse({"status": "PENDING"}))
    with pytest.raises(RuntimeError):
        tasks.start_validation("http://api:8001", http, {})


def test_poll_validation_completes():
    http = FakeHttpClient(
        get_responses=[
            FakeResponse({"validation_id": "v", "status": "RUNNING"}),
            FakeResponse({"validation_id": "v", "status": "COMPLETED", "invalid_count": 0}),
        ]
    )
    result = tasks.poll_validation("http://api:8001", http, "v", sleep_fn=lambda _: None)
    assert result["status"] == "COMPLETED"


def test_poll_validation_times_out():
    http = FakeHttpClient(get_responses=[FakeResponse({"status": "RUNNING"})])
    with pytest.raises(TimeoutError):
        tasks.poll_validation("http://api:8001", http, "v", max_polls=2, sleep_fn=lambda _: None)


def test_evaluate_validation_ok():
    summary = tasks.evaluate_validation(
        {"validation_id": "v", "status": "COMPLETED", "invalid_count": 0, "valid_count": 100}
    )
    assert summary["ok"] is True
    assert summary["valid_count"] == 100


def test_evaluate_validation_too_many_invalid_raises():
    with pytest.raises(RuntimeError):
        tasks.evaluate_validation(
            {"validation_id": "v", "status": "COMPLETED", "invalid_count": 3}, max_invalid=2
        )


def test_evaluate_validation_within_tolerance_ok():
    summary = tasks.evaluate_validation(
        {"validation_id": "v", "status": "COMPLETED", "invalid_count": 2}, max_invalid=2
    )
    assert summary["invalid_count"] == 2


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED"])
def test_evaluate_validation_non_success_raises(status):
    with pytest.raises(RuntimeError):
        tasks.evaluate_validation({"validation_id": "v", "status": status})
