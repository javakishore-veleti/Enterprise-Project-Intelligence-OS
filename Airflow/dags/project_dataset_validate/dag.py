"""Airflow DAG: project dataset validation.

Task flow::

    build_validation_request -> start_validation -> poll_validation
        -> evaluate_validation

The DAG is a thin operational wrapper: every task delegates to a pure callable
in :mod:`tasks`, injecting ``requests`` as the HTTP client and the Ingestion-API
base URL from the ``INGESTION_API_BASE_URL`` env var. No database access and no
agent/LLM logic live here — validation is driven exclusively through the
Ingestion-API FastAPI boundary.

NOTE: the validation endpoints this DAG calls are the *intended* Ingestion-API
contract and are **not yet implemented** in the middleware. See ``tasks.py``
PENDING markers.

Triggered on demand (``schedule=None``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_dataset_validate import tasks

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
    "max_invalid": 0,
    "run_id": None,
}


@dag(
    dag_id="project_dataset_validate",
    description="Validate imported dataset records via the Ingestion-API.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    tags=["ingestion", "operational", "validate"],
    doc_md=__doc__,
)
def project_dataset_validate():
    @task
    def build_validation_request(**context):
        params = context["params"]
        return tasks.build_validation_request(
            dataset_id=params["dataset_id"],
            requested_by=params["requested_by"],
            max_invalid=params["max_invalid"],
            run_id=params.get("run_id"),
        )

    @task
    def start_validation(request):
        return tasks.start_validation(
            base_url=tasks.get_base_url(),
            http=requests,
            request=request,
        )

    @task
    def poll_validation(validation):
        payload = tasks.poll_validation(
            base_url=tasks.get_base_url(),
            http=requests,
            validation_id=validation["validation_id"],
        )
        payload.setdefault("validation_id", validation["validation_id"])
        return payload

    @task
    def evaluate_validation(payload, **context):
        params = context["params"]
        return tasks.evaluate_validation(payload, max_invalid=params["max_invalid"])

    request = build_validation_request()
    validation = start_validation(request)
    terminal = poll_validation(validation)
    evaluate_validation(terminal)


dag = project_dataset_validate()
