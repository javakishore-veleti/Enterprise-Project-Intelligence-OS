"""PostgreSQL-backed persistence of ingestion sub-operations."""
from __future__ import annotations

import json

from ingestion_api.daos.connection import Database
from ingestion_api.dtos.common import OperationRecord
from ingestion_api.interfaces.daos import OperationsDao

_COLUMNS = "operation_id, op_type, dataset_id, status, params, result, created_at, updated_at"


def _obj(v):
    if isinstance(v, str):
        v = json.loads(v)
    return dict(v or {})


def _row(r: tuple) -> OperationRecord:
    return OperationRecord(
        operation_id=r[0], op_type=r[1], dataset_id=r[2], status=r[3],
        params=_obj(r[4]), result=_obj(r[5]), created_at=r[6], updated_at=r[7],
    )


class PostgresOperationsDao(OperationsDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def insert(self, record: OperationRecord) -> OperationRecord:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO ingestion.operations ({_COLUMNS}) "
                "VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) "
                f"RETURNING {_COLUMNS}",
                (
                    record.operation_id, record.op_type, record.dataset_id, record.status,
                    json.dumps(record.params), json.dumps(record.result),
                    record.created_at, record.updated_at,
                ),
            )
            return _row(cur.fetchone())

    def get(self, operation_id: str) -> OperationRecord | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM ingestion.operations WHERE operation_id = %s",
                (operation_id,),
            )
            row = cur.fetchone()
            return _row(row) if row else None

    def update_result(self, operation_id: str, status: str, result: dict) -> OperationRecord | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE ingestion.operations SET status = %s, result = %s::jsonb, updated_at = now() "
                f"WHERE operation_id = %s RETURNING {_COLUMNS}",
                (status, json.dumps(result), operation_id),
            )
            row = cur.fetchone()
            return _row(row) if row else None
