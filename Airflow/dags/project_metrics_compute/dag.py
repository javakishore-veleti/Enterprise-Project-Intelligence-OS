"""Airflow DAG: recompute deterministic project metrics from ingested evidence.

Task flow::

    list_projects -> compute (dynamic-mapped, one per project, in parallel)

Run after ingestion (on demand or scheduled). Delegates the deterministic
computation to the Projects-API (``POST /projects/{key}/metrics/compute``), which
reads the evidence store and upserts ``project_metrics``. No metric logic or LLM
lives in the DAG — it only fans out over projects.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_metrics_compute import tasks

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}


@dag(
    dag_id="project_metrics_compute",
    description="Recompute project metrics from ingested evidence via the Projects-API.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["metrics", "operational"],
    doc_md=__doc__,
)
def project_metrics_compute():
    @task
    def list_projects() -> list[str]:
        return tasks.list_project_keys(tasks.get_base_url(), requests)

    @task
    def compute(project_key: str) -> dict:
        return tasks.compute_project(tasks.get_base_url(), requests, project_key)

    compute.expand(project_key=list_projects())


dag = project_metrics_compute()
