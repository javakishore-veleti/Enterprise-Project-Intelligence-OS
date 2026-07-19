"""Unit tests for the scheduled per-project risk analysis DAG (hermetic)."""

from pathlib import Path

import pytest

from project_risk_schedule import tasks

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
    assert "project_risk_schedule" in dag_bag.dags


def test_dag_structure_and_schedule():
    from airflow.models import DagBag

    dag_bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    dag = dag_bag.dags["project_risk_schedule"]

    # Cron schedule (daily) — not on-demand.
    assert dag.schedule_interval == "0 6 * * *"
    assert set(dag.task_ids) == {"resolve_projects", "analyze_project", "summarize"}
    assert dag.get_task("analyze_project").upstream_task_ids == {"resolve_projects"}
    assert dag.get_task("summarize").upstream_task_ids == {"analyze_project"}
    assert dag.default_args["retries"] == 2


def test_get_base_url_default(monkeypatch):
    monkeypatch.delenv("RISK_ANALYTICS_API_BASE_URL", raising=False)
    assert tasks.get_base_url() == "http://localhost:8004"


def test_get_base_url_from_env_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("RISK_ANALYTICS_API_BASE_URL", "http://risk:8004/")
    assert tasks.get_base_url() == "http://risk:8004"


def test_resolve_projects_normalises():
    assert tasks.resolve_projects([" APACHE ", "SPARK"]) == ["APACHE", "SPARK"]


@pytest.mark.parametrize("bad", [[], ["APACHE", ""], ["  "]])
def test_resolve_projects_invalid(bad):
    with pytest.raises(ValueError):
        tasks.resolve_projects(bad)


def test_start_project_analysis_posts_correct_body():
    http = FakeHttpClient(
        post_response=FakeResponse(
            {
                "run_id": "run-9",
                "project_key": "APACHE",
                "status": "COMPLETED",
                "findings": [{"finding_id": "f1"}, {"finding_id": "f2"}],
            }
        )
    )
    result = tasks.start_project_analysis(
        "http://risk:8004", http, "APACHE", ["schedule_risk"], "airflow"
    )
    assert result == {
        "project_key": "APACHE",
        "run_id": "run-9",
        "status": "COMPLETED",
        "finding_count": 2,
    }
    call = http.post_calls[0]
    assert call["url"] == "http://risk:8004/api/v1/analysis/projects/APACHE"
    assert call["json"] == {"agents": ["schedule_risk"], "requested_by": "airflow"}


def test_start_project_analysis_missing_run_id_raises():
    http = FakeHttpClient(post_response=FakeResponse({"status": "COMPLETED"}))
    with pytest.raises(RuntimeError):
        tasks.start_project_analysis("http://risk:8004", http, "APACHE", [])


def test_start_project_analysis_propagates_http_error():
    boom = RuntimeError("503 Service Unavailable")
    http = FakeHttpClient(post_response=FakeResponse({}, 503, boom))
    with pytest.raises(RuntimeError, match="503"):
        tasks.start_project_analysis("http://risk:8004", http, "APACHE", [])


def test_start_project_analysis_requires_project_key():
    http = FakeHttpClient(post_response=FakeResponse({"run_id": "x"}))
    with pytest.raises(ValueError):
        tasks.start_project_analysis("http://risk:8004", http, "", [])


def test_summarize_all_completed():
    results = [
        {"project_key": "A", "status": "COMPLETED", "finding_count": 2},
        {"project_key": "B", "status": "COMPLETED", "finding_count": 3},
    ]
    summary = tasks.summarize(results)
    assert summary["total"] == 2
    assert summary["completed"] == 2
    assert summary["failed"] == 0
    assert summary["total_findings"] == 5


def test_summarize_raises_when_any_incomplete():
    results = [
        {"project_key": "A", "status": "COMPLETED", "finding_count": 2},
        {"project_key": "B", "status": "FAILED", "finding_count": 0},
    ]
    with pytest.raises(RuntimeError, match="did not complete"):
        tasks.summarize(results)
