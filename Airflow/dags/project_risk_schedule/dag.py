"""Airflow DAG: scheduled per-project risk analysis.

Task flow (with dynamic task mapping, one analyze task per project)::

    resolve_projects -> analyze_project (expanded per project) -> summarize

The DAG is a thin operational wrapper: every task delegates to a pure callable
in :mod:`tasks`, injecting ``requests`` as the HTTP client and the
RiskAnalytics-API base URL from the ``RISK_ANALYTICS_API_BASE_URL`` env var. No
database access and no agent/LLM logic live here — risk analysis is driven
exclusively through the RiskAnalytics-API FastAPI boundary, which owns the
LangGraph multi-agent orchestration.

Endpoint: ``POST /api/v1/analysis/projects/{project_key}`` EXISTS today; body
``{"agents": [...], "requested_by": "airflow"}``.

Runs on a daily cron schedule.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_risk_schedule import tasks

DEFAULT_ARGS = {
    "owner": "risk-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}

DEFAULT_PARAMS = {
    # The configured set of projects to analyse on each scheduled run.
    "project_keys": ["APACHE", "SPARK", "KAFKA"],
    # Agent keys to run; empty means the middleware runs its configured default set.
    "agents": [],
    "requested_by": "airflow",
}


@dag(
    dag_id="project_risk_schedule",
    description="Scheduled multi-agent risk analysis per project via the RiskAnalytics-API.",
    schedule="0 6 * * *",  # daily at 06:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    tags=["risk", "scheduled", "analysis"],
    doc_md=__doc__,
)
def project_risk_schedule():
    @task
    def resolve_projects(**context):
        params = context["params"]
        return tasks.resolve_projects(params["project_keys"])

    @task
    def analyze_project(project_key, **context):
        params = context["params"]
        return tasks.start_project_analysis(
            base_url=tasks.get_base_url(),
            http=requests,
            project_key=project_key,
            agents=params["agents"],
            requested_by=params["requested_by"],
        )

    @task
    def summarize(results):
        return tasks.summarize(results)

    projects = resolve_projects()
    # Dynamic task mapping: one analysis task instance per configured project.
    results = analyze_project.expand(project_key=projects)
    summarize(results)


dag = project_risk_schedule()
