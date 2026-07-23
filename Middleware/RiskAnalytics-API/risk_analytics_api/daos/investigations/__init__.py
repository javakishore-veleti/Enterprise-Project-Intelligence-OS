"""PostgreSQL-backed persistence of Investigation Agent runs.

History is a newest-first list capped at the most recent 100 rows: the total is
``LEAST(count(*), 100)`` and the read path never pages past offset 100, so the
list/total can never exceed 100. Scope (``requested_by``) and a case-insensitive
``q`` (project_key/question/root_cause ILIKE ``%q%``) filter the window in SQL.
"""
from __future__ import annotations

import json

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.responses import (
    EvidenceCitation,
    InvestigationRecord,
    InvestigationResponse,
    InvestigationStep,
    InvestigationSummary,
    InvestigationsPageResponse,
)
from risk_analytics_api.interfaces.daos import InvestigationDao

#: Hard ceiling on the history: the list + total never exceed this.
HISTORY_CAP = 100

_INSERT_COLUMNS = (
    "investigation_id, project_key, requested_by, question, template_key, status, "
    "root_cause, confidence, recommended_action, hypotheses, causal_chain, steps, "
    "evidence, run_id, created_at"
)
_FULL_COLUMNS = _INSERT_COLUMNS
_SUMMARY_COLUMNS = (
    "investigation_id, project_key, question, template_key, status, "
    "root_cause, confidence, created_at"
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
        clauses.append(
            "(project_key ILIKE %s OR question ILIKE %s OR root_cause ILIKE %s)"
        )
        like = f"%{q}%"
        params.extend([like, like, like])
    if projects:
        clauses.append("project_key = ANY(%s)")
        params.append(list(projects))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


class PostgresInvestigationDao(InvestigationDao):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def insert_investigation(self, record: InvestigationRecord) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO risk.investigations ({_INSERT_COLUMNS}) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)",
                (
                    record.investigation_id, record.project_key, record.requested_by,
                    record.question, record.template_key, record.status,
                    record.root_cause, record.confidence, record.recommended_action,
                    json.dumps(list(record.hypotheses)),
                    json.dumps(list(record.causal_chain)),
                    json.dumps([s.model_dump() for s in record.steps]),
                    json.dumps([e.model_dump() for e in record.evidence]),
                    record.run_id, record.created_at,
                ),
            )

    def list_investigations(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> InvestigationsPageResponse:
        where, params = _scope_clause(scope, q, projects)
        # Clamp so the list + total never exceed the newest HISTORY_CAP rows.
        eff_offset = max(0, min(offset, HISTORY_CAP))
        eff_limit = max(0, min(limit, HISTORY_CAP))
        if eff_offset + eff_limit > HISTORY_CAP:
            eff_limit = HISTORY_CAP - eff_offset

        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT LEAST(count(*), {HISTORY_CAP}) FROM risk.investigations{where}",
                tuple(params),
            )
            total = int(cur.fetchone()[0])
            rows = []
            if eff_limit > 0:
                cur.execute(
                    f"SELECT {_SUMMARY_COLUMNS} FROM risk.investigations{where} "
                    "ORDER BY created_at DESC, investigation_id LIMIT %s OFFSET %s",
                    tuple(params) + (eff_limit, eff_offset),
                )
                rows = cur.fetchall()
        items = [_to_summary(r) for r in rows]
        return InvestigationsPageResponse(
            total=total, returned=len(items), offset=offset, limit=limit, items=items
        )

    def get_investigation(self, investigation_id: str) -> InvestigationResponse | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_FULL_COLUMNS} FROM risk.investigations WHERE investigation_id = %s",
                (investigation_id,),
            )
            row = cur.fetchone()
        return _to_response(row) if row is not None else None


def _to_summary(r: tuple) -> InvestigationSummary:
    # pg8000 returns the uuid PK as a UUID object; the DTO is a string.
    return InvestigationSummary(
        investigation_id=str(r[0]), project_key=r[1], question=r[2], template_key=r[3],
        status=r[4], root_cause=r[5], confidence=r[6], created_at=r[7],
    )


def _to_response(r: tuple) -> InvestigationResponse:
    # r[2] is requested_by (persisted but not surfaced on the conclusion DTO).
    return InvestigationResponse(
        investigation_id=str(r[0]), project_key=r[1],
        question=r[3], template_key=r[4], status=r[5],
        root_cause=r[6] or "", confidence=float(r[7]) if r[7] is not None else 0.0,
        recommended_action=r[8] or "",
        hypotheses=[str(h) for h in _jsonlist(r[9])],
        causal_chain=[str(c) for c in _jsonlist(r[10])],
        steps=[InvestigationStep(**s) for s in _jsonlist(r[11])],
        evidence=[EvidenceCitation(**e) for e in _jsonlist(r[12])],
        run_id=r[13], generated_at=r[14],
    )
