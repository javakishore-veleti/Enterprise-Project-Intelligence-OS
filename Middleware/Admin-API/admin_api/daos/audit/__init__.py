"""PostgreSQL-backed implementation of the append-only audit DAO."""
from __future__ import annotations

import json

from admin_api.daos.connection import Database
from admin_api.dtos.responses import AuditEventResponse
from admin_api.interfaces.daos import AuditDao

_COLUMNS = "event_id, entity_type, entity_key, action, actor, details, created_at"


def _row(r: tuple) -> AuditEventResponse:
    details = r[5]
    if isinstance(details, str):  # pg8000 may return jsonb as text
        details = json.loads(details)
    return AuditEventResponse(
        event_id=r[0],
        entity_type=r[1],
        entity_key=r[2],
        action=r[3],
        actor=r[4],
        details=details or {},
        created_at=r[6],
    )


class PostgresAuditDao(AuditDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def append(self, event: AuditEventResponse) -> AuditEventResponse:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO admin.audit_events "
                f"({_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s) "
                f"RETURNING {_COLUMNS}",
                (
                    event.event_id,
                    event.entity_type,
                    event.entity_key,
                    event.action,
                    event.actor,
                    json.dumps(event.details),
                    event.created_at,
                ),
            )
            return _row(cur.fetchone())

    def list(self, limit, offset):
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM admin.audit_events")
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {_COLUMNS} FROM admin.audit_events "
                "ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            return [_row(r) for r in cur.fetchall()], total
