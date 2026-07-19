"""Unit tests for the scheduled portfolio-level risk analysis DAG (hermetic)."""

from pathlib import Path

import pytest

from portfolio_risk_schedule import tasks

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
    def __init__(self, post_response=None):
        self._post_response = post_response
        self.post_calls = []

    def post(self, url, json, timeout):  # noqa: A002
        self.post_calls.append({"url": url, "json": json, "timeout": timeout})
        return self._post_response


def test_dagbag_imports_without_errors():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert dag_bag.import_errors == {}, f"DAG import errors: {dag_bag.import_errors}"
    assert "portfolio_risk_schedule" in dag_bag.dags


def test_dag_structure_and_schedule():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    dag = dag_bag.dags["portfolio_risk_schedule"]

    assert dag.schedule_interval == "0 7 * * 1"  # weekly cron
    assert set(dag.task_ids) == {
        "build_portfolio_request",
        "start_portfolio_analysis",
        "finalize",
    }
    assert dag.get_task("start_portfolio_analysis").upstream_task_ids == {
        "build_portfolio_request"
    }
    assert dag.get_task("finalize").upstream_task_ids == {"start_portfolio_analysis"}
    assert dag.default_args["retries"] == 2


def test_get_base_url_default(monkeypatch):
    monkeypatch.delenv("RISK_ANALYTICS_API_BASE_URL", raising=False)
    assert tasks.get_base_url() == "http://localhost:8004"


def test_build_portfolio_request_valid():
    req = tasks.build_portfolio_request(" ALL ", ["executive_reporting"], "airflow")
    assert req == {
        "portfolio_key": "ALL",
        "agents": ["executive_reporting"],
        "requested_by": "airflow",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"portfolio_key": "", "agents": [], "requested_by": "x"},
        {"portfolio_key": "   ", "agents": [], "requested_by": "x"},
        {"portfolio_key": "ALL", "agents": [], "requested_by": ""},
    ],
)
def test_build_portfolio_request_invalid(kwargs):
    with pytest.raises(ValueError):
        tasks.build_portfolio_request(**kwargs)


def test_start_portfolio_analysis_posts_correct_body():
    http = FakeHttpClient(
        post_response=FakeResponse(
            {
                "run_id": "run-1",
                "portfolio_key": "ALL",
                "status": "COMPLETED",
                "findings": [{"finding_id": "f1"}],
                "project_count": 42,
            }
        )
    )
    req = {"portfolio_key": "ALL", "agents": ["executive_reporting"], "requested_by": "airflow"}
    result = tasks.start_portfolio_analysis("http://risk:8004", http, req)
    assert result == {
        "portfolio_key": "ALL",
        "run_id": "run-1",
        "status": "COMPLETED",
        "finding_count": 1,
        "project_count": 42,
    }
    call = http.post_calls[0]
    assert call["url"] == "http://risk:8004/api/v1/analysis/portfolios/ALL"
    assert call["json"] == {"agents": ["executive_reporting"], "requested_by": "airflow"}


def test_start_portfolio_analysis_missing_run_id_raises():
    http = FakeHttpClient(post_response=FakeResponse({"status": "COMPLETED"}))
    req = {"portfolio_key": "ALL", "agents": [], "requested_by": "airflow"}
    with pytest.raises(RuntimeError):
        tasks.start_portfolio_analysis("http://risk:8004", http, req)


def test_finalize_completed_ok():
    summary = tasks.finalize(
        {"portfolio_key": "ALL", "run_id": "r", "status": "COMPLETED", "finding_count": 3}
    )
    assert summary == {
        "portfolio_key": "ALL",
        "run_id": "r",
        "status": "COMPLETED",
        "finding_count": 3,
        "ok": True,
    }


@pytest.mark.parametrize("status", ["FAILED", "RUNNING"])
def test_finalize_non_success_raises(status):
    with pytest.raises(RuntimeError):
        tasks.finalize({"portfolio_key": "ALL", "status": status})
