"""Airflow DAG: ``tracker_repository_sync`` — sync an org's tracker repo into evidence.

Map structure (concurrent at BOTH levels via dynamic task mapping)::

    start ─▶ plan.expand(project=…) ─▶ flatten ─▶ sync_batch.expand(spec=…) ─▶ finalize

- ``start``      — read conf, build the connector, list projects, register them as
  ``tracker_projects``, and record the run (projects_intended/considered).
- ``plan``       — mapped PER PROJECT (parallel): count issues, compute bounded
  batch windows, skip already-committed batches (resume), record the project row.
- ``flatten``    — collect the per-project plans into ONE flat list of batch specs.
- ``sync_batch`` — mapped PER BATCH across all projects (parallel): fetch the
  window, normalize+stamp+upsert evidence, commit the batch checkpoint (atomic
  project-counter bump; project flips COMPLETED when its last batch lands).
- ``finalize``   — reconcile the run status from the project rollups.

So many projects sync in parallel AND a single large project's batches sync in
parallel. Every batch is an independent, idempotent unit (upsert by issue_key),
so concurrent batches never corrupt each other and a re-run is safe.

Correlation: the Ingestion-API generates ``sync_run_id`` and triggers this DAG
with it as the ``dag_run_id`` + a conf key, so ``dag_run.run_id == sync_run_id``
and all tracking rows key off it. The daily schedule runs the end-of-day delta
(``since`` = the last completed run's watermark, resolved by the Ingestion-API).

Concurrency is bounded by ``max_active_tasks`` (DAG) + ``max_active_tis_per_dag``
(per mapped task) + an Airflow pool, all env-configurable, so a huge project can't
overwhelm Mongo/Postgres.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from tracker_sync import tasks
from tracker_sync.sync_engine import sync_batch_window
from tracker_sync.writers import MongoEvidenceWriter, OrgApiProjectRegistrar

DEFAULT_ARGS = {
    "owner": "data-platform", "depends_on_past": False, "retries": 2,
    "retry_delay": timedelta(minutes=1), "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
}
DEFAULT_PARAMS = {
    "repo_id": "", "org_id": "", "root_org_id": "", "provider": "fake",
    "connection_config": {}, "since": None, "batch_size": 500, "requested_by": "system",
}
BATCH_SIZE = int(os.environ.get("TRACKER_SYNC_BATCH_SIZE", "500"))
# Bound parallel batch/project tasks so a huge project can't overwhelm the stores.
MAX_ACTIVE_TIS = int(os.environ.get("TRACKER_SYNC_MAX_ACTIVE", "8"))
POOL = os.environ.get("TRACKER_SYNC_POOL", "default_pool")


def _conf(context) -> dict:
    dr = context.get("dag_run")
    return (dr.conf if dr and dr.conf else None) or {}


def _sync_run_id(context) -> str:
    # sync_run_id == dag_run_id (the Ingestion-API set the run_id on trigger).
    return _conf(context).get("sync_run_id") or context["run_id"]


def _repo_ctx(context) -> dict:
    conf = _conf(context)
    params = context["params"]
    return {
        "repo_id": conf.get("repo_id") or params["repo_id"],
        "org_id": conf.get("org_id") or params["org_id"],
        "root_org_id": conf.get("root_org_id") or params["root_org_id"],
        "provider": conf.get("provider") or params["provider"],
        "connection_config": conf.get("connection_config") or params["connection_config"] or {},
    }


def _mark_failed(context) -> None:
    try:
        tasks.finalize_run(tasks.get_ingestion_base_url(), requests,
                           _sync_run_id(context), "FAILED", message="Sync failed; see Airflow logs.")
    except Exception:  # pragma: no cover
        pass


@dag(dag_id="tracker_repository_sync",
     description="Sync an org's tracker repository into the evidence store (batched, resumable).",
     schedule="0 22 * * *",  # daily 22:00 — end-of-day delta (since = last completed run)
     start_date=datetime(2026, 1, 1), catchup=False,
     default_args=DEFAULT_ARGS, params=DEFAULT_PARAMS, on_failure_callback=_mark_failed,
     max_active_tasks=MAX_ACTIVE_TIS, tags=["sync", "operational", "tracker"], doc_md=__doc__)
def tracker_repository_sync():
    @task
    def start(**context) -> dict:
        base = tasks.get_ingestion_base_url()
        sync_run_id = _sync_run_id(context)
        repo_ctx = _repo_ctx(context)
        since_iso = _conf(context).get("since") or context["params"].get("since")
        client, staging = tasks.open_staging_db()
        try:
            connector = tasks.build_connector(repo_ctx["provider"], staging)
            projects = connector.list_projects(repo_ctx["connection_config"])
        finally:
            client.close()
        keys = [p["external_key"] for p in projects]
        # Register discovered projects as tracker_projects under the repo (idempotent).
        OrgApiProjectRegistrar(tasks.get_org_api_base_url(), requests).register(
            repo_ctx["repo_id"], projects)
        # projects_intended == what we planned to import; projects_considered == what the
        # connector actually listed (same here, but distinct concepts for real trackers).
        tasks.record_run_projects(base, requests, sync_run_id,
                                  projects_intended=keys, projects_considered=len(keys))
        return {"sync_run_id": sync_run_id, "repo_ctx": repo_ctx,
                "since": since_iso, "projects": keys}

    @task
    def project_keys(started: dict) -> list[str]:
        # A plain-list XCom the per-project ``plan`` task can map over.
        return started["projects"]

    @task(max_active_tis_per_dag=MAX_ACTIVE_TIS, pool=POOL)
    def plan(project_key: str, ctx: dict, **context) -> list[dict]:
        base = tasks.get_ingestion_base_url()
        sync_run_id = ctx["sync_run_id"]
        repo_ctx = ctx["repo_ctx"]
        since = tasks.parse_since(ctx.get("since"))
        client, staging = tasks.open_staging_db()
        try:
            connector = tasks.build_connector(repo_ctx["provider"], staging)
            total = connector.count_issues(repo_ctx["connection_config"], project_key, since=since)
        finally:
            client.close()
        already = tasks.committed_batches(base, requests, sync_run_id, project_key)
        specs = tasks.build_batch_specs(project_key, total, BATCH_SIZE, already)
        # Record the project row with its planned totals (batches_total drives COMPLETED).
        import math
        batches_total = math.ceil(total / BATCH_SIZE) if total else 0
        tasks.plan_project(base, requests, sync_run_id, project_key,
                           issues_intended=total, batches_total=batches_total)
        # Enrich each window into a self-contained batch spec for the per-batch expand.
        return [{"sync_run_id": sync_run_id, "repo_ctx": repo_ctx, "since": ctx.get("since"),
                 "project_key": project_key, **spec} for spec in specs]

    @task
    def flatten(plans: list[list[dict]]) -> list[dict]:
        # Collapse the per-project plan lists into ONE flat list so sync_batch can
        # fan out per batch across ALL projects at once.
        return [spec for plan_list in plans for spec in (plan_list or [])]

    @task(max_active_tis_per_dag=MAX_ACTIVE_TIS, pool=POOL)
    def sync_batch(spec: dict, **context) -> dict:
        base = tasks.get_ingestion_base_url()
        repo_ctx = spec["repo_ctx"]
        since = tasks.parse_since(spec.get("since"))
        client, staging = tasks.open_staging_db()
        try:
            connector = tasks.build_connector(repo_ctx["provider"], staging)
            writer = MongoEvidenceWriter(client[os.environ.get("MONGO_DATABASE", "epi_os")], repo_ctx)
            window = {"batch_no": spec["batch_no"], "offset": spec["offset"], "limit": spec["limit"]}
            result = sync_batch_window(connector, repo_ctx, spec["project_key"], window, writer, since)
        finally:
            client.close()
        # Commit the checkpoint + atomically bump the project's counters (governed).
        tasks.record_batch(base, requests, spec["sync_run_id"], spec["project_key"],
                           batch_no=result["batch_no"], source_offset=result["source_offset"],
                           record_count=result["record_count"])
        return result

    @task(trigger_rule="all_done")
    def finalize(results, started: dict, **context) -> None:
        # The Ingestion-API reconciles run status from the project rollups
        # (COMPLETED iff every project COMPLETED, else FAILED).
        tasks.finalize_run(tasks.get_ingestion_base_url(), requests,
                           started["sync_run_id"], "COMPLETED", message="Sync tasks finished.")

    started = start()
    keys = project_keys(started)
    plans = plan.partial(ctx=started).expand(project_key=keys)
    specs = flatten(plans)
    results = sync_batch.expand(spec=specs)
    finalize(results, started)


dag = tracker_repository_sync()
