"""Airflow DAG: project dataset reconciliation.

Task flow::

    build_reconcile_request -> start_reconciliation -> poll_reconciliation
        -> evaluate_reconciliation

The DAG is a thin operational wrapper: every task delegates to a pure callable
in :mod:`tasks`, injecting ``requests`` as the HTTP client and the Ingestion-API
base URL from the ``INGESTION_API_BASE_URL`` env var. No database access and no
agent/LLM logic live here — reconciliation is driven exclusively through the
Ingestion-API FastAPI boundary.

NOTE: the reconciliation endpoints this DAG calls are the *intended* Ingestion-API
contract and are **not yet implemented** in the middleware. See ``tasks.py``
PENDING markers.

Triggered on demand (``schedule=None``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_dataset_reconcile import tasks

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
    "requested_by": "airflow",
    "entities": ["projects", "issues", "histories", "comments", "links"],
    "run_id": None,
}


@dag(
    dag_id="project_dataset_reconcile",
    description="Reconcile source vs destination record counts via the Ingestion-API.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    tags=["ingestion", "operational", "reconcile"],
    doc_md=__doc__,
)
def project_dataset_reconcile():
    @task
    def build_reconcile_request(**context):
        params = context["params"]
        return tasks.build_reconcile_request(
            dataset_id=params["dataset_id"],
            requested_by=params["requested_by"],
            entities=params.get("entities"),
            run_id=params.get("run_id"),
        )

    @task
    def start_reconciliation(request):
        return tasks.start_reconciliation(
            base_url=tasks.get_base_url(),
            http=requests,
            request=request,
        )

    @task
    def poll_reconciliation(reconciliation):
        payload = tasks.poll_reconciliation(
            base_url=tasks.get_base_url(),
            http=requests,
            reconciliation_id=reconciliation["reconciliation_id"],
        )
        payload.setdefault("reconciliation_id", reconciliation["reconciliation_id"])
        return payload

    @task
    def evaluate_reconciliation(payload):
        return tasks.evaluate_reconciliation(payload)

    request = build_reconcile_request()
    reconciliation = start_reconciliation(request)
    terminal = poll_reconciliation(reconciliation)
    evaluate_reconciliation(terminal)


dag = project_dataset_reconcile()
