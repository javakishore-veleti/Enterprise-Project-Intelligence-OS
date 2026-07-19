"""Airflow DAG: real, batched, resumable dataset ingestion.

Task flow::

    prepare -> load_entity (dynamic-mapped, one per entity, in parallel) -> finalize

Triggered on demand (``schedule=None``), typically by the Admin portal
"Ingest into evidence store" button via the Ingestion-API (which creates the run
and POSTs a dagRun with ``conf = {dataset_id, run_id}``). The DAG:

1. ``prepare``     — extract the downloaded archive; discover per-entity JSON-lines files.
2. ``load_entity`` — for each entity (mapped/parallel): stream the file in bounded
   batches, upsert each batch into MongoDB (idempotent), skip already-committed
   batches (resume), and report a checkpoint + progress per batch to the Ingestion-API.
3. ``finalize``    — mark the run COMPLETED (or FAILED via the failure hook).

Evidence writes go straight to Mongo (throughput); run/batch/log status is
governed through the Ingestion-API. The whole dataset is never held in memory.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_dataset_ingest import tasks

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}

DEFAULT_PARAMS = {"dataset_id": "public-jira"}
BATCH_SIZE = int(os.environ.get("INGEST_BATCH_SIZE", "1000"))


def _conf(context) -> dict:
    dag_run = context.get("dag_run")
    return (dag_run.conf if dag_run else None) or {}


def _mark_failed(context) -> None:
    conf = _conf(context)
    run_id = conf.get("run_id")
    if not run_id:
        return
    try:
        tasks.finalize_run(tasks.get_base_url(), requests, run_id, "FAILED",
                           message="Ingestion failed; see Airflow logs.")
    except Exception:  # pragma: no cover - best effort
        pass


@dag(
    dag_id="project_dataset_ingest",
    description="Extract + batch-ingest the dataset into MongoDB with durable checkpoints.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    on_failure_callback=_mark_failed,
    tags=["ingestion", "operational", "batch"],
    doc_md=__doc__,
)
def project_dataset_ingest():
    @task
    def prepare(**context) -> list[dict]:
        conf = _conf(context)
        dataset_id = conf.get("dataset_id", context["params"]["dataset_id"])
        base = tasks.get_base_url()
        dataset = tasks.fetch_dataset(base, requests, dataset_id)
        data_dir = os.environ.get("DATASET_DATA_DIR", "/opt/airflow/data")
        zip_path = dataset.get("downloaded_path") or os.path.join(data_dir, dataset["file_name"])
        work_dir = os.path.join(data_dir, "extracted", dataset_id)
        tasks.extract_archive(zip_path, work_dir)
        return [
            {"entity": entity, "path": path, "total": total}
            for entity, path, total in tasks.discover_entities(work_dir)
        ]

    @task
    def load_entity(spec: dict, **context) -> dict:
        from pymongo import MongoClient

        run_id = _conf(context)["run_id"]
        base = tasks.get_base_url()
        client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/epi_os"))
        try:
            db = client[os.environ.get("MONGO_DATABASE", "epi_os")]
            coll = db[spec["entity"]]
            key = tasks.natural_key(spec["entity"])
            already = tasks.committed_batches(base, requests, run_id, spec["entity"])
            done = 0
            for batch_no, offset, records in tasks.iter_batches(spec["path"], BATCH_SIZE):
                done += len(records)
                if batch_no in already:
                    continue  # resume: skip committed batch
                tasks.upsert_batch(coll, records, key)
                tasks.report_batch(base, requests, run_id, entity=spec["entity"], batch_no=batch_no,
                                   source_offset=offset, record_count=len(records),
                                   records_done=done, records_total=spec["total"],
                                   message=f"{spec['entity']} batch {batch_no}")
            return {"entity": spec["entity"], "records": done}
        finally:
            client.close()

    @task(trigger_rule="all_done")
    def finalize(loaded, **context) -> None:
        run_id = _conf(context).get("run_id")
        if run_id:
            tasks.finalize_run(tasks.get_base_url(), requests, run_id, "COMPLETED",
                               message="Ingestion complete.")

    specs = prepare()
    loaded = load_entity.expand(spec=specs)
    finalize(loaded)


dag = project_dataset_ingest()
