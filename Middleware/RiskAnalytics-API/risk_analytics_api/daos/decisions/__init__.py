"""PostgreSQL-backed persistence of Decide runs (Options-first decision support).

Structurally mirrors ``daos/forecasts``: history is a newest-first list capped at
the most recent 100 rows (total is ``LEAST(count(*), 100)`` and the read path never
pages past offset 100). Scope (``requested_by``) and a case-insensitive ``q``
(project_key/narrative ILIKE ``%q%``) filter the window in SQL. The uuid PK is cast
to ``str`` in the row mappers (pg8000 returns it as a UUID object — a real bug
otherwise).

Unlike the forecast DAO this table is mutated after creation: a decision is
inserted DRAFTED, then updated on select (status SELECTED + selected_option_id)
and approve (status APPROVED + approved_at).
"""
from __future__ import annotations

import json
from datetime import datetime

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.responses import (
    DecisionOption,
    DecisionRecord,
    DecisionResponse,
    DecisionsPageResponse,
    DecisionSummary,
)
from risk_analytics_api.interfaces.daos import DecisionDao

#: Hard ceiling on the history: the list + total never exceed this.
HISTORY_CAP = 100

_INSERT_COLUMNS = (
    "decision_id, project_key, requested_by, status, options, selected_option_id, "
    "narrative, confidence, run_id, created_at, approved_at"
)
_FULL_COLUMNS = _INSERT_COLUMNS
_SUMMARY_COLUMNS = (
    "decision_id, project_key, status, selected_option_id, confidence, options, created_at"
)


def _jsonlist(v) -> list:
    if isinstance(v, str):
        v = json.loads(v)
    return list(v or [])


def _scope_clause(
    scope: str | None, q: str | None, projects: list[str] | None = None
) -> tuple[str, list]:
    """Build a parameterised WHERE clause for scope + case-insensitive search +
    an optional project_key IN (...) filter (server-side, parameterized)."""
    clauses: list[str] = []
    params: list = []
    if scope:
        clauses.append("requested_by = %s")
        params.append(scope)
    if q:
        clauses.append("(project_key ILIKE %s OR narrative ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
    if projects:
        clauses.append("project_key = ANY(%s)")
        params.append(list(projects))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


class PostgresDecisionDao(DecisionDao):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def insert_decision(self, record: DecisionRecord) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO risk.decisions ({_INSERT_COLUMNS}) VALUES "
                "(%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)",
                (
                    record.decision_id, record.project_key, record.requested_by,
                    record.status,
                    json.dumps([o.model_dump() for o in record.options]),
                    record.selected_option_id, record.narrative, record.confidence,
                    record.run_id, record.created_at, record.approved_at,
                ),
            )

    def update_selection(self, decision_id: str, option_id: str, status: str) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE risk.decisions SET selected_option_id = %s, status = %s "
                "WHERE decision_id = %s",
                (option_id, status, decision_id),
            )

    def update_approval(self, decision_id: str, status: str, approved_at: datetime) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE risk.decisions SET status = %s, approved_at = %s "
                "WHERE decision_id = %s",
                (status, approved_at, decision_id),
            )

    def list_decisions(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> DecisionsPageResponse:
        where, params = _scope_clause(scope, q, projects)
        eff_offset = max(0, min(offset, HISTORY_CAP))
        eff_limit = max(0, min(limit, HISTORY_CAP))
        if eff_offset + eff_limit > HISTORY_CAP:
            eff_limit = HISTORY_CAP - eff_offset

        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT LEAST(count(*), {HISTORY_CAP}) FROM risk.decisions{where}",
                tuple(params),
            )
            total = int(cur.fetchone()[0])
            rows = []
            if eff_limit > 0:
                cur.execute(
                    f"SELECT {_SUMMARY_COLUMNS} FROM risk.decisions{where} "
                    "ORDER BY created_at DESC, decision_id LIMIT %s OFFSET %s",
                    tuple(params) + (eff_limit, eff_offset),
                )
                rows = cur.fetchall()
        items = [_to_summary(r) for r in rows]
        return DecisionsPageResponse(
            total=total, returned=len(items), offset=offset, limit=limit, items=items
        )

    def get_decision(self, decision_id: str) -> DecisionResponse | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_FULL_COLUMNS} FROM risk.decisions WHERE decision_id = %s",
                (decision_id,),
            )
            row = cur.fetchone()
        return _to_response(row) if row is not None else None


def _to_summary(r: tuple) -> DecisionSummary:
    return DecisionSummary(
        decision_id=str(r[0]), project_key=r[1], status=r[2],
        selected_option_id=r[3],
        confidence=float(r[4]) if r[4] is not None else None,
        option_count=len(_jsonlist(r[5])),
        created_at=r[6],
    )


def _to_response(r: tuple) -> DecisionResponse:
    # Column order mirrors _INSERT_COLUMNS. r[2] is requested_by (not surfaced).
    return DecisionResponse(
        decision_id=str(r[0]), project_key=r[1], question=None,
        status=r[3],
        options=[DecisionOption(**o) for o in _jsonlist(r[4])],
        selected_option_id=r[5],
        narrative=r[6] or "",
        confidence=float(r[7]) if r[7] is not None else 0.0,
        run_id=r[8], created_at=r[9], approved_at=r[10],
    )
