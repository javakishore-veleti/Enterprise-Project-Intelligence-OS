"""PostgreSQL-backed implementation of the ingestion-tracking DAO."""
from __future__ import annotations

from ingestion_api.daos.connection import Database
from ingestion_api.dtos.common import IngestionStatus
from ingestion_api.dtos.responses import IngestionRunResponse
from ingestion_api.interfaces.daos import IngestionTrackingDao

_COLUMNS = "run_id, dataset_id, status, batch_size, parallelism, requested_by, created_at, updated_at"


def _row_to_response(row: tuple) -> IngestionRunResponse:
    return IngestionRunResponse(
        run_id=row[0],
        dataset_id=row[1],
        status=IngestionStatus(row[2]),
        batch_size=row[3],
        parallelism=row[4],
        requested_by=row[5],
        created_at=row[6],
        updated_at=row[7],
    )


class PostgresIngestionTrackingDao(IngestionTrackingDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def insert_run(self, run: IngestionRunResponse) -> IngestionRunResponse:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO ingestion.ingestion_runs ({_COLUMNS}) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                f"RETURNING {_COLUMNS}",
                (
                    run.run_id,
                    run.dataset_id,
                    run.status.value,
                    run.batch_size,
                    run.parallelism,
                    run.requested_by,
                    run.created_at,
                    run.updated_at,
                ),
            )
            return _row_to_response(cur.fetchone())

    def get_run(self, run_id: str) -> IngestionRunResponse | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM ingestion.ingestion_runs WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
            return _row_to_response(row) if row else None

    def update_status(self, run_id: str, status: IngestionStatus) -> IngestionRunResponse | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE ingestion.ingestion_runs SET status = %s, updated_at = now() "
                f"WHERE run_id = %s RETURNING {_COLUMNS}",
                (status.value, run_id),
            )
            row = cur.fetchone()
            return _row_to_response(row) if row else None
