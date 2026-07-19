"""Unit tests for the project dataset reconciliation DAG (hermetic)."""

from pathlib import Path

import pytest

from project_dataset_reconcile import tasks

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
    assert "project_dataset_reconcile" in dag_bag.dags


def test_dag_structure_and_schedule():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    dag = dag_bag.dags["project_dataset_reconcile"]

    assert dag.schedule_interval is None
    assert set(dag.task_ids) == {
        "build_reconcile_request",
        "start_reconciliation",
        "poll_reconciliation",
        "evaluate_reconciliation",
    }
    assert dag.get_task("start_reconciliation").upstream_task_ids == {"build_reconcile_request"}
    assert dag.get_task("poll_reconciliation").upstream_task_ids == {"start_reconciliation"}
    assert dag.get_task("evaluate_reconciliation").upstream_task_ids == {"poll_reconciliation"}
    assert dag.default_args["retries"] == 3


def test_get_base_url_default(monkeypatch):
    monkeypatch.delenv("INGESTION_API_BASE_URL", raising=False)
    assert tasks.get_base_url() == "http://localhost:8001"


def test_build_reconcile_request_valid_with_entities():
    req = tasks.build_reconcile_request("ds", "airflow", entities=["issues"], run_id="r-1")
    assert req == {
        "dataset_id": "ds",
        "requested_by": "airflow",
        "entities": ["issues"],
        "run_id": "r-1",
    }


def test_build_reconcile_request_omits_optionals():
    req = tasks.build_reconcile_request("ds", "airflow")
    assert req == {"dataset_id": "ds", "requested_by": "airflow"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dataset_id": "", "requested_by": "x"},
        {"dataset_id": "d", "requested_by": ""},
    ],
)
def test_build_reconcile_request_invalid(kwargs):
    with pytest.raises(ValueError):
        tasks.build_reconcile_request(**kwargs)


def test_start_reconciliation_posts_and_returns_id():
    http = FakeHttpClient(
        post_response=FakeResponse({"reconciliation_id": "rc-1", "status": "PENDING"})
    )
    req = {"dataset_id": "d", "requested_by": "x"}
    result = tasks.start_reconciliation("http://api:8001", http, req)
    assert result == {"reconciliation_id": "rc-1", "status": "PENDING"}
    assert http.post_calls[0]["url"] == "http://api:8001/api/v1/ingestion/reconciliations"


def test_start_reconciliation_missing_id_raises():
    http = FakeHttpClient(post_response=FakeResponse({"status": "PENDING"}))
    with pytest.raises(RuntimeError):
        tasks.start_reconciliation("http://api:8001", http, {})


def test_poll_reconciliation_completes():
    http = FakeHttpClient(
        get_responses=[
            FakeResponse({"reconciliation_id": "rc", "status": "RUNNING"}),
            FakeResponse(
                {
                    "reconciliation_id": "rc",
                    "status": "COMPLETED",
                    "source_count": 10,
                    "destination_count": 10,
                    "mismatches": [],
                }
            ),
        ]
    )
    result = tasks.poll_reconciliation("http://api:8001", http, "rc", sleep_fn=lambda _: None)
    assert result["status"] == "COMPLETED"


def test_poll_reconciliation_times_out():
    http = FakeHttpClient(get_responses=[FakeResponse({"status": "RUNNING"})])
    with pytest.raises(TimeoutError):
        tasks.poll_reconciliation(
            "http://api:8001", http, "rc", max_polls=2, sleep_fn=lambda _: None
        )


def test_evaluate_reconciliation_matched_ok():
    summary = tasks.evaluate_reconciliation(
        {
            "reconciliation_id": "rc",
            "status": "COMPLETED",
            "source_count": 10,
            "destination_count": 10,
            "mismatches": [],
        }
    )
    assert summary["matched"] is True
    assert summary["source_count"] == 10


def test_evaluate_reconciliation_mismatch_raises():
    with pytest.raises(RuntimeError):
        tasks.evaluate_reconciliation(
            {
                "reconciliation_id": "rc",
                "status": "COMPLETED",
                "mismatches": [{"entity": "issues", "source": 10, "destination": 9}],
            }
        )


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED"])
def test_evaluate_reconciliation_non_success_raises(status):
    with pytest.raises(RuntimeError):
        tasks.evaluate_reconciliation({"reconciliation_id": "rc", "status": status})
