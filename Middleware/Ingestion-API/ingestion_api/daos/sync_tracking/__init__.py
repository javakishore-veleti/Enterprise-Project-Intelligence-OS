"""PostgreSQL-backed tracker-sync tracking log (run / project / batch).

Concurrency safety is the whole point here: many batch tasks (across projects and
within a project) commit in parallel, so the project counters are bumped with
ATOMIC SQL increments (``batches_done = batches_done + 1``), never read-modify-write
in Python — no lost updates. A project flips to COMPLETED the moment its own last
batch lands (the CASE reads the post-increment value), and the run is reconciled
from the project rollups at finalize. Batch commits are idempotent via
``ON CONFLICT DO NOTHING`` on ``(sync_run_id, project_key, batch_no)``, so a
re-delivered/retried batch never double-counts.
"""
from __future__ import annotations

import json
from datetime import datetime

from ingestion_api.common.utilities import new_id
from ingestion_api.daos.connection import Database
from ingestion_api.dtos.responses import SyncBatchInfo, SyncProjectProgress
from ingestion_api.interfaces.daos import SyncTrackingDao

_RUN_COLS = (
    "sync_run_id, repo_id, org_id, root_org_id, provider, since, status, "
    "projects_intended, projects_considered, projects_total, issues_total, "
    "requested_by, message, started_at, completed_at, updated_at"
)


def _run_to_dict(row: tuple) -> dict:
    intended = row[7]
    if isinstance(intended, str):
        intended = json.loads(intended)
    return {
        "sync_run_id": row[0], "repo_id": row[1], "org_id": row[2], "root_org_id": row[3],
        "provider": row[4], "since": row[5], "status": row[6],
        "projects_intended": list(intended or []), "projects_considered": row[8],
        "projects_total": row[9], "issues_total": row[10], "requested_by": row[11],
        "message": row[12], "started_at": row[13], "completed_at": row[14], "updated_at": row[15],
    }


class PostgresSyncTrackingDao(SyncTrackingDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def insert_run(self, sync_run_id, repo_id, org_id, root_org_id, provider,
                   since, requested_by) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ingestion.sync_runs "
                "(sync_run_id, repo_id, org_id, root_org_id, provider, since, status, requested_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'RUNNING', %s)",
                (sync_run_id, repo_id, org_id, root_org_id, provider, since, requested_by),
            )

    def get_run(self, sync_run_id: str) -> dict | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_RUN_COLS} FROM ingestion.sync_runs WHERE sync_run_id = %s",
                (sync_run_id,))
            row = cur.fetchone()
            return _run_to_dict(row) if row else None

    def latest_run_for_repo(self, repo_id: str) -> dict | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_RUN_COLS} FROM ingestion.sync_runs "
                "WHERE repo_id = %s ORDER BY started_at DESC LIMIT 1", (repo_id,))
            row = cur.fetchone()
            return _run_to_dict(row) if row else None

    def last_completed_watermark(self, repo_id: str) -> datetime | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT started_at FROM ingestion.sync_runs "
                "WHERE repo_id = %s AND status = 'COMPLETED' "
                "ORDER BY started_at DESC LIMIT 1", (repo_id,))
            row = cur.fetchone()
            return row[0] if row else None

    def set_run_projects(self, sync_run_id, projects_intended, projects_considered) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE ingestion.sync_runs SET projects_intended = %s::jsonb, "
                "projects_considered = %s, updated_at = now() WHERE sync_run_id = %s",
                (json.dumps(list(projects_intended)), projects_considered, sync_run_id))

    def upsert_project_plan(self, sync_run_id, project_key, issues_intended, batches_total) -> None:
        # A project with zero planned batches is COMPLETED immediately (nothing to import).
        # On a retry, preserve the accumulated batches_done/issues_imported.
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ingestion.sync_run_projects "
                "(sync_run_id, project_key, status, issues_intended, batches_total, started_at) "
                "VALUES (%s, %s, %s, %s, %s, now()) "
                "ON CONFLICT (sync_run_id, project_key) DO UPDATE SET "
                "  issues_intended = EXCLUDED.issues_intended, "
                "  batches_total = EXCLUDED.batches_total, "
                "  status = CASE "
                "    WHEN EXCLUDED.batches_total = 0 THEN 'COMPLETED' "
                "    WHEN ingestion.sync_run_projects.batches_done >= EXCLUDED.batches_total THEN 'COMPLETED' "
                "    ELSE 'IN_PROGRESS' END, "
                "  updated_at = now()",
                (sync_run_id, project_key,
                 "COMPLETED" if batches_total == 0 else "IN_PROGRESS",
                 issues_intended, batches_total))

    def committed_batch_numbers(self, sync_run_id, project_key) -> set[int]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT batch_no FROM ingestion.sync_batches "
                "WHERE sync_run_id = %s AND project_key = %s", (sync_run_id, project_key))
            return {r[0] for r in cur.fetchall()}

    def commit_batch(self, sync_run_id, project_key, batch_no, source_offset, record_count) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            # Idempotent insert: a re-delivered batch does nothing (no double count).
            cur.execute(
                "INSERT INTO ingestion.sync_batches "
                "(batch_id, sync_run_id, project_key, batch_no, source_offset, record_count, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'COMMITTED') "
                "ON CONFLICT (sync_run_id, project_key, batch_no) DO NOTHING "
                "RETURNING batch_id",
                (new_id(), sync_run_id, project_key, batch_no, source_offset, record_count))
            if cur.fetchone() is None:
                return  # already committed -> idempotent no-op
            # Atomic counter bump + status roll-up (reads the post-increment value).
            cur.execute(
                "UPDATE ingestion.sync_run_projects SET "
                "  batches_done = batches_done + 1, "
                "  issues_imported = issues_imported + %s, "
                "  started_at = COALESCE(started_at, now()), "
                "  status = CASE WHEN batches_total > 0 AND batches_done + 1 >= batches_total "
                "                THEN 'COMPLETED' ELSE 'IN_PROGRESS' END, "
                "  completed_at = CASE WHEN batches_total > 0 AND batches_done + 1 >= batches_total "
                "                      THEN now() ELSE completed_at END, "
                "  updated_at = now() "
                "WHERE sync_run_id = %s AND project_key = %s",
                (record_count, sync_run_id, project_key))
            cur.execute(
                "UPDATE ingestion.sync_runs SET issues_total = issues_total + %s, "
                "updated_at = now() WHERE sync_run_id = %s",
                (record_count, sync_run_id))

    def finalize_run(self, sync_run_id, status, message) -> dict | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*), COUNT(*) FILTER (WHERE status = 'COMPLETED') "
                "FROM ingestion.sync_run_projects WHERE sync_run_id = %s", (sync_run_id,))
            total, completed = cur.fetchone()
            # Explicit FAILED wins; otherwise COMPLETED iff every project completed.
            if status == "FAILED":
                derived = "FAILED"
            else:
                derived = "COMPLETED" if total > 0 and completed == total else "FAILED"
            cur.execute(
                "UPDATE ingestion.sync_runs SET status = %s, projects_total = %s, "
                "message = %s, completed_at = now(), updated_at = now() "
                f"WHERE sync_run_id = %s RETURNING {_RUN_COLS}",
                (derived, completed, message, sync_run_id))
            row = cur.fetchone()
            return _run_to_dict(row) if row else None

    def project_progress(self, sync_run_id: str) -> list[SyncProjectProgress]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT project_key, status, issues_intended, issues_imported, "
                "batches_total, batches_done, started_at, completed_at "
                "FROM ingestion.sync_run_projects WHERE sync_run_id = %s ORDER BY project_key",
                (sync_run_id,))
            return [SyncProjectProgress(
                project_key=r[0], status=r[1], issues_intended=r[2], issues_imported=r[3],
                batches_total=r[4], batches_done=r[5], started_at=r[6], completed_at=r[7])
                for r in cur.fetchall()]

    def recent_batches(self, sync_run_id: str, limit: int) -> list[SyncBatchInfo]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT project_key, batch_no, source_offset, record_count, status, attempts, updated_at "
                "FROM ingestion.sync_batches WHERE sync_run_id = %s "
                "ORDER BY updated_at DESC LIMIT %s", (sync_run_id, limit))
            return [SyncBatchInfo(
                project_key=r[0], batch_no=r[1], source_offset=r[2], record_count=r[3],
                status=r[4], attempts=r[5], updated_at=r[6]) for r in cur.fetchall()]
