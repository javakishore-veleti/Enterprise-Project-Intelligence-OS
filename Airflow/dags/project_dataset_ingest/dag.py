"""Airflow DAG: real dataset ingestion (mongorestore + normalize).

Task flow::

    prepare -> restore -> discover -> normalize (dynamic-mapped per repo) -> finalize

The public Jira dataset is a MongoDB dump, so ingestion:
1. ``prepare``   — extract the downloaded zip; locate the ``*.archive`` mongodump.
2. ``restore``   — ``mongorestore`` the gzipped archive into the ``jira_repos`` staging DB.
3. ``discover``  — list the restored repo collections (one per Jira project).
4. ``normalize`` — per repo (parallel): stream issues in bounded batches, transform
   each into our evidence collections (issues/histories/comments/links), idempotent
   upsert, skip already-committed batches (resume), report checkpoints/progress.
5. ``finalize``  — mark the run COMPLETED (which auto-triggers metric computation).

Requires ``mongorestore`` (mongodb-database-tools) on the Airflow worker; evidence
writes go straight to Mongo, status stays governed via the Ingestion-API.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from project_dataset_ingest import tasks

DEFAULT_ARGS = {
    "owner": "data-platform", "depends_on_past": False, "retries": 2,
    "retry_delay": timedelta(minutes=2), "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}
DEFAULT_PARAMS = {"dataset_id": "public-jira"}
BATCH_SIZE = int(os.environ.get("INGEST_BATCH_SIZE", "1000"))
EVIDENCE_DB = os.environ.get("MONGO_DATABASE", "epi_os")


def _conf(context) -> dict:
    dr = context.get("dag_run")
    return (dr.conf if dr else None) or {}


def _mark_failed(context) -> None:
    run_id = _conf(context).get("run_id")
    if run_id:
        try:
            tasks.finalize_run(tasks.get_base_url(), requests, run_id, "FAILED",
                               message="Ingestion failed; see Airflow logs.")
        except Exception:  # pragma: no cover
            pass


@dag(dag_id="project_dataset_ingest",
     description="mongorestore the Jira dump + normalize issues into the evidence store.",
     schedule=None, start_date=datetime(2026, 1, 1), catchup=False,
     default_args=DEFAULT_ARGS, params=DEFAULT_PARAMS, on_failure_callback=_mark_failed,
     tags=["ingestion", "operational", "batch"], doc_md=__doc__)
def project_dataset_ingest():
    @task
    def prepare(**context) -> dict:
        dataset_id = _conf(context).get("dataset_id", context["params"]["dataset_id"])
        base = tasks.get_base_url()
        dataset = tasks.fetch_dataset(base, requests, dataset_id)
        data_dir = os.environ.get("DATASET_DATA_DIR", "/opt/airflow/data")
        zip_path = dataset.get("downloaded_path") or os.path.join(data_dir, dataset["file_name"])
        work_dir = os.path.join(data_dir, "extracted", dataset_id)
        tasks.extract_archive(zip_path, work_dir)
        # Optional bounded ingest: conf {"repos": ["Mindville", ...]} restores only
        # those repos (e.g. when disk can't hold the full ~60 GB). None = all repos.
        return {"dataset_id": dataset_id, "run_id": _conf(context).get("run_id"),
                "repos": _conf(context).get("repos"),
                "archive_path": tasks.find_mongodump_archive(work_dir)}

    @task
    def restore(prep: dict) -> dict:
        cmd = tasks.build_mongorestore_cmd(prep["archive_path"], tasks.get_mongo_uri(),
                                           repos=prep.get("repos"))
        tasks.run_mongorestore(cmd)
        return prep

    @task
    def discover(prep: dict) -> list[dict]:
        from pymongo import MongoClient
        client = MongoClient(tasks.get_mongo_uri())
        try:
            staging = client[tasks.STAGING_DB]
            specs = []
            for name in staging.list_collection_names():
                specs.append({"entity": name, "total": staging[name].estimated_document_count()})
            return sorted(specs, key=lambda s: s["entity"])
        finally:
            client.close()

    @task
    def normalize(spec: dict, **context) -> dict:
        from pymongo import MongoClient
        run_id = _conf(context)["run_id"]
        base = tasks.get_base_url()
        client = MongoClient(tasks.get_mongo_uri())
        try:
            staging = client[tasks.STAGING_DB]
            evidence = client[EVIDENCE_DB]
            entity = spec["entity"]
            already = tasks.committed_batches(base, requests, run_id, entity)
            done = 0
            coverage = {"docs": 0, "unmapped": 0, "present": {}}
            for batch_no, offset, docs in tasks.iter_issue_batches(staging[entity], BATCH_SIZE):
                done += len(docs)
                if batch_no in already:
                    continue
                bcov = tasks.batch_coverage(docs)
                coverage = tasks.merge_coverage(coverage, bcov) if coverage["docs"] else bcov
                tasks.upsert_evidence(evidence, entity, docs)
                # WARN (through the governed log) the moment a batch has docs whose
                # shape transform_issue can't map — a real-restore mapping mismatch.
                unmapped = bcov["unmapped"]
                tasks.report_batch(base, requests, run_id, entity=entity, batch_no=batch_no,
                                   source_offset=offset, record_count=len(docs),
                                   records_done=done, records_total=spec["total"],
                                   message=(f"{entity} batch {batch_no}" if not unmapped
                                            else f"{entity} batch {batch_no}: {unmapped}/{len(docs)} docs unmapped (schema mismatch?)"),
                                   level="WARNING" if unmapped else "INFO")
            return {"entity": entity, "records": done, "coverage": coverage}
        finally:
            client.close()

    @task(trigger_rule="all_done")
    def finalize(loaded, **context) -> None:
        run_id = _conf(context).get("run_id")
        if run_id:
            tasks.finalize_run(tasks.get_base_url(), requests, run_id, "COMPLETED",
                               message="Ingestion complete.")

    prepared = prepare()
    restored = restore(prepared)
    specs = discover(restored)
    loaded = normalize.expand(spec=specs)
    finalize(loaded)


dag = project_dataset_ingest()
