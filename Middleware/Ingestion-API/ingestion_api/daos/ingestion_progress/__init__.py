"""PostgreSQL-backed batch checkpoints + progress log."""
from __future__ import annotations

from ingestion_api.common.utilities import new_id
from ingestion_api.daos.connection import Database
from ingestion_api.interfaces.daos import IngestionProgressDao


class PostgresIngestionProgressDao(IngestionProgressDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def record_batch(self, run_id, entity, batch_no, source_offset, record_count,
                     records_done, records_total, level, message) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            # Idempotent checkpoint per (run, entity, batch_no): a re-delivered
            # batch bumps attempts instead of duplicating.
            cur.execute(
                "INSERT INTO ingestion.ingestion_batches "
                "(batch_id, run_id, entity, batch_no, source_offset, record_count, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'COMMITTED') "
                "ON CONFLICT (run_id, entity, batch_no) DO UPDATE SET "
                "  source_offset = EXCLUDED.source_offset,"
                "  record_count = EXCLUDED.record_count,"
                "  attempts = ingestion.ingestion_batches.attempts + 1,"
                "  updated_at = now()",
                (new_id(), run_id, entity, batch_no, source_offset, record_count),
            )
            cur.execute(
                "INSERT INTO ingestion.ingestion_log "
                "(log_id, run_id, level, entity, message, records_done, records_total) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (new_id(), run_id, level, entity, message, records_done, records_total),
            )

    def committed_batch_numbers(self, run_id: str, entity: str) -> set[int]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT batch_no FROM ingestion.ingestion_batches "
                "WHERE run_id = %s AND entity = %s",
                (run_id, entity),
            )
            return {r[0] for r in cur.fetchall()}

    def entity_progress(self, run_id: str) -> list[tuple[str, int, int]]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT ON (entity) entity, records_done, records_total "
                "FROM ingestion.ingestion_log "
                "WHERE run_id = %s AND entity IS NOT NULL "
                "ORDER BY entity, created_at DESC",
                (run_id,),
            )
            return [(r[0], r[1], r[2]) for r in cur.fetchall()]

    def recent_log(self, run_id: str, limit: int) -> list[tuple]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT level, entity, message, records_done, records_total, created_at "
                "FROM ingestion.ingestion_log WHERE run_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (run_id, limit),
            )
            return list(cur.fetchall())
