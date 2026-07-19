"""Airflow DAG: real project dataset acquisition.

Task flow::

    prepare -> download -> complete

Triggered on demand (``schedule=None``), typically by the Admin portal
"Initial Dataset" button via the Ingestion-API (which POSTs a dagRun with a
``conf`` carrying ``dataset_id``). The DAG:

1. ``prepare``  — GET the dataset metadata from the Ingestion-API and mark it DOWNLOADING.
2. ``download`` — stream the archive from its source URL to ``DATASET_DATA_DIR``,
   verifying md5 (idempotent: skips if already present with a matching checksum).
3. ``complete`` — mark the dataset DOWNLOADED with the path + byte count.

All state lives in the Ingestion-API (the governed boundary); the DAG only does
operational work. On failure the dataset is marked FAILED.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_dataset_acquire import tasks

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}

DEFAULT_PARAMS = {"dataset_id": "public-jira"}


def _mark_failed(context) -> None:
    """DAG-level failure hook: mark the dataset FAILED in the Ingestion-API."""
    dag_run = context.get("dag_run")
    conf = (dag_run.conf if dag_run else None) or {}
    dataset_id = conf.get("dataset_id") or DEFAULT_PARAMS["dataset_id"]
    try:
        tasks.update_status(
            tasks.get_base_url(), requests, dataset_id, "FAILED",
            message="Acquisition failed; see Airflow logs.",
        )
    except Exception:  # pragma: no cover - best-effort status update
        pass


@dag(
    dag_id="project_dataset_acquire",
    description="Download + checksum-verify the dataset archive; report status to the Ingestion-API.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    on_failure_callback=_mark_failed,
    tags=["ingestion", "operational", "acquire"],
    doc_md=__doc__,
)
def project_dataset_acquire():
    @task
    def prepare(**context) -> dict:
        dataset_id = context["params"]["dataset_id"]
        base = tasks.get_base_url()
        dataset = tasks.fetch_dataset(base, requests, dataset_id)
        tasks.update_status(base, requests, dataset_id, "DOWNLOADING",
                            downloaded_bytes=0, message="Download started.")
        return {"dataset_id": dataset_id, "source_url": dataset["source_url"],
                "expected_md5": dataset["expected_md5"], "file_name": dataset["file_name"]}

    @task
    def download(dataset: dict) -> dict:
        import os
        dest = os.path.join(tasks.get_data_dir(), dataset["file_name"])
        result = tasks.download_dataset(
            dataset["source_url"], dest, requests, expected_md5=dataset["expected_md5"],
        )
        tasks.verify_md5(result["md5"], dataset["expected_md5"])
        result["dataset_id"] = dataset["dataset_id"]
        return result

    @task
    def complete(result: dict) -> dict:
        tasks.update_status(
            tasks.get_base_url(), requests, result["dataset_id"], "DOWNLOADED",
            downloaded_bytes=result["bytes"], downloaded_path=result["path"],
            message="Skipped (already present)." if result.get("skipped") else "Download complete.",
        )
        return result

    complete(download(prepare()))


dag = project_dataset_acquire()
