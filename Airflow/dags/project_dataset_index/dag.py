"""Airflow DAG: project dataset index creation.

Task flow::

    build_index_request -> start_indexing -> poll_indexing -> finalize

The DAG is a thin operational wrapper: every task delegates to a pure callable
in :mod:`tasks`, injecting ``requests`` as the HTTP client and the Ingestion-API
base URL from the ``INGESTION_API_BASE_URL`` env var. No database access and no
agent/LLM logic live here — index creation is driven exclusively through the
Ingestion-API FastAPI boundary (the middleware issues the actual DDL).

NOTE: the indexing endpoints this DAG calls are the *intended* Ingestion-API
contract and are **not yet implemented** in the middleware. See ``tasks.py``
PENDING markers.

Triggered on demand (``schedule=None``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_dataset_index import tasks

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
}

DEFAULT_PARAMS = {
    "dataset_id": "msr-issue-tracking",
    "targets": ["projects", "issues", "histories", "comments", "links"],
    "requested_by": "airflow",
    "concurrently": True,
}


@dag(
    dag_id="project_dataset_index",
    description="Create database indexes for the imported dataset via the Ingestion-API.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    tags=["ingestion", "operational", "index"],
    doc_md=__doc__,
)
def project_dataset_index():
    @task
    def build_index_request(**context):
        params = context["params"]
        return tasks.build_index_request(
            dataset_id=params["dataset_id"],
            targets=params["targets"],
            requested_by=params["requested_by"],
            concurrently=params["concurrently"],
        )

    @task
    def start_indexing(request):
        return tasks.start_indexing(
            base_url=tasks.get_base_url(),
            http=requests,
            request=request,
        )

    @task
    def poll_indexing(index_job):
        payload = tasks.poll_indexing(
            base_url=tasks.get_base_url(),
            http=requests,
            index_job_id=index_job["index_job_id"],
        )
        payload.setdefault("index_job_id", index_job["index_job_id"])
        return payload

    @task
    def finalize(payload):
        return tasks.finalize(payload)

    request = build_index_request()
    index_job = start_indexing(request)
    terminal = poll_indexing(index_job)
    finalize(terminal)


dag = project_dataset_index()
