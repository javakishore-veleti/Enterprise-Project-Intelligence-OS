"""Airflow DAG: project dataset acquisition.

Task flow::

    build_acquire_spec -> start_acquisition -> poll_acquisition
        -> verify_checksum -> extract_dataset -> finalize

The DAG is a thin operational wrapper: every task delegates to a pure callable
in :mod:`tasks`, injecting ``requests`` as the HTTP client and the Ingestion-API
base URL from the ``INGESTION_API_BASE_URL`` env var. No database access and no
agent/LLM logic live here — acquisition is driven exclusively through the
Ingestion-API FastAPI boundary.

NOTE: the acquisition/verify/extract endpoints this DAG calls are the *intended*
Ingestion-API contract and are **not yet implemented** in the middleware (only
``/api/v1/ingestion/runs`` exists today). See ``tasks.py`` PENDING markers.

Triggered on demand (``schedule=None``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_dataset_acquire import tasks

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
    "source_url": "https://zenodo.org/records/15719919/files/dataset.tar.gz",
    "expected_sha256": "0" * 64,
    "requested_by": "airflow",
}


@dag(
    dag_id="project_dataset_acquire",
    description="Acquire, checksum-verify, and extract the dataset via the Ingestion-API.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    tags=["ingestion", "operational", "acquire"],
    doc_md=__doc__,
)
def project_dataset_acquire():
    @task
    def build_acquire_spec(**context):
        params = context["params"]
        return tasks.build_acquire_spec(
            dataset_id=params["dataset_id"],
            source_url=params["source_url"],
            expected_sha256=params["expected_sha256"],
            requested_by=params["requested_by"],
        )

    @task
    def start_acquisition(spec):
        return tasks.start_acquisition(
            base_url=tasks.get_base_url(),
            http=requests,
            spec=spec,
        )

    @task
    def poll_acquisition(acquisition):
        payload = tasks.poll_acquisition(
            base_url=tasks.get_base_url(),
            http=requests,
            acquisition_id=acquisition["acquisition_id"],
        )
        payload.setdefault("acquisition_id", acquisition["acquisition_id"])
        return payload

    @task
    def verify_checksum(acquisition_payload, **context):
        params = context["params"]
        tasks.verify_checksum(
            base_url=tasks.get_base_url(),
            http=requests,
            acquisition_id=acquisition_payload["acquisition_id"],
            expected_sha256=params["expected_sha256"],
        )
        return acquisition_payload

    @task
    def extract_dataset(acquisition_payload):
        result = tasks.extract_dataset(
            base_url=tasks.get_base_url(),
            http=requests,
            acquisition_id=acquisition_payload["acquisition_id"],
        )
        result["acquisition_id"] = acquisition_payload["acquisition_id"]
        return result

    @task
    def finalize(extract_payload):
        return tasks.finalize(
            acquisition_id=extract_payload["acquisition_id"],
            extract_payload=extract_payload,
        )

    spec = build_acquire_spec()
    acquisition = start_acquisition(spec)
    downloaded = poll_acquisition(acquisition)
    verified = verify_checksum(downloaded)
    extracted = extract_dataset(verified)
    finalize(extracted)


dag = project_dataset_acquire()
