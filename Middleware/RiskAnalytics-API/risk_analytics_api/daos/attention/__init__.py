"""PostgreSQL-backed scoped/time-aware reads for the attention feed.

The feed can span dozens of projects, so the DAO does the scope + as_of
filtering in SQL and returns only a bounded, newest-first window (``cap``) for
the service to score in Python; a separate COUNT gives the true in-scope total
for "view more" pagination.
"""
from __future__ import annotations

import json
from datetime import datetime

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.responses import AttentionFindingRow
from risk_analytics_api.interfaces.daos import AttentionDao

_SELECT_COLUMNS = (
    "finding_id, run_id, project_key, agent_key, risk_category, severity, "
    "score, probability, confidence, explanation, recommended_actions, analysis_timestamp"
)


def _scope_clause(
    as_of_end: datetime | None, projects: list[str] | None
) -> tuple[str, list]:
    """Build a safe parameterised WHERE clause for scope + as_of (pg8000 format style)."""
    clauses: list[str] = []
    params: list = []
    if as_of_end is not None:
        clauses.append("analysis_timestamp < %s")
        params.append(as_of_end)
    if projects is not None:
        clauses.append("project_key = ANY(%s)")
        params.append(list(projects))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


class PostgresAttentionDao(AttentionDao):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def count(self, as_of_end: datetime | None, projects: list[str] | None) -> int:
        where, params = _scope_clause(as_of_end, projects)
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT count(*) FROM risk.risk_findings{where}", tuple(params))
            row = cur.fetchone()
        return int(row[0])

    def distinct_projects(
        self, as_of_end: datetime | None, projects: list[str] | None
    ) -> int:
        where, params = _scope_clause(as_of_end, projects)
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT count(DISTINCT project_key) FROM risk.risk_findings{where}",
                tuple(params),
            )
            row = cur.fetchone()
        return int(row[0])

    def window(
        self, as_of_end: datetime | None, projects: list[str] | None, cap: int
    ) -> list[AttentionFindingRow]:
        where, params = _scope_clause(as_of_end, projects)
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_SELECT_COLUMNS} FROM risk.risk_findings{where} "
                "ORDER BY analysis_timestamp DESC, finding_id LIMIT %s",
                tuple(params) + (cap,),
            )
            rows = cur.fetchall()
        return [_to_row(r) for r in rows]


def _to_row(r) -> AttentionFindingRow:
    actions = r[10]
    if isinstance(actions, str):
        actions = json.loads(actions)
    return AttentionFindingRow(
        finding_id=r[0], run_id=r[1], project_key=r[2], agent_key=r[3],
        risk_category=r[4], severity=r[5], score=r[6], probability=r[7],
        confidence=r[8], explanation=r[9] or "",
        recommended_actions=[str(a) for a in (actions or [])],
        analysis_timestamp=r[11],
    )
