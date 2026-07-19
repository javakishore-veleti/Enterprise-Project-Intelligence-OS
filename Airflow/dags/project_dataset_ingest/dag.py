"""Airflow DAG: project dataset ingestion.

Task flow::

    read_metadata -> check_disk_space -> start_ingestion -> poll_status -> finalize

The DAG is a thin operational wrapper: every task delegates to a pure callable
in :mod:`tasks`, injecting ``requests`` as the HTTP client and the
Ingestion-API base URL from the ``INGESTION_API_BASE_URL`` env var. No database
access and no agent/LLM logic live here — ingestion is driven exclusively
through the Ingestion-API FastAPI boundary.

Triggered on demand (``schedule=None``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_dataset_ingest import tasks

# Minimum free disk (bytes) required before we request an ingestion run.
DEFAULT_MIN_FREE_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB

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
    "batch_size": 1000,
    "parallelism": 4,
    "requested_by": "airflow",
    "min_free_bytes": DEFAULT_MIN_FREE_BYTES,
}


@dag(
    dag_id="project_dataset_ingest",
    description="Trigger and monitor dataset ingestion via the Ingestion-API.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    tags=["ingestion", "operational"],
    doc_md=__doc__,
)
def project_dataset_ingest():
    @task
    def read_metadata(**context):
        params = context["params"]
        return tasks.read_metadata(
            dataset_id=params["dataset_id"],
            batch_size=params["batch_size"],
            parallelism=params["parallelism"],
            requested_by=params["requested_by"],
        )

    @task
    def check_disk_space(metadata, **context):
        params = context["params"]
        tasks.check_disk_space(min_free_bytes=params["min_free_bytes"])
        return metadata

    @task
    def start_ingestion(metadata):
        return tasks.start_ingestion(
            base_url=tasks.get_base_url(),
            http=requests,
            metadata=metadata,
        )

    @task
    def poll_status(run):
        payload = tasks.poll_status(
            base_url=tasks.get_base_url(),
            http=requests,
            run_id=run["run_id"],
        )
        # Carry the run_id through in case the status resource omits it.
        payload.setdefault("run_id", run["run_id"])
        return payload

    @task
    def finalize(run_payload):
        return tasks.finalize(run_payload)

    metadata = read_metadata()
    checked = check_disk_space(metadata)
    run = start_ingestion(checked)
    terminal = poll_status(run)
    finalize(terminal)


dag = project_dataset_ingest()
