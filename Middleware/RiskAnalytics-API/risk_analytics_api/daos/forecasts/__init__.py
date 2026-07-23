"""PostgreSQL-backed persistence of delivery-forecast runs.

Structurally identical to ``daos/investigations``: history is a newest-first list
capped at the most recent 100 rows (total is ``LEAST(count(*), 100)`` and the read
path never pages past offset 100). Scope (``requested_by``) and a case-insensitive
``q`` (project_key/narrative ILIKE ``%q%``) filter the window in SQL. The uuid PK
is cast to ``str`` in the row mappers (pg8000 returns it as a UUID object).
"""
from __future__ import annotations

import json

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.responses import (
    ForecastDriver,
    ForecastRecord,
    ForecastResponse,
    ForecastSummary,
    ForecastsPageResponse,
)
from risk_analytics_api.interfaces.daos import ForecastDao

#: Hard ceiling on the history: the list + total never exceed this.
HISTORY_CAP = 100

_INSERT_COLUMNS = (
    "forecast_id, project_key, requested_by, status, on_time_probability, "
    "probability_low, probability_high, projected_slip_days_low, projected_slip_days_high, "
    "outlook, drivers, bull_case, bear_case, would_change_mind, narrative, confidence, "
    "run_id, created_at, subject_type, subject_value"
)
_FULL_COLUMNS = _INSERT_COLUMNS
_SUMMARY_COLUMNS = (
    "forecast_id, project_key, on_time_probability, outlook, "
    "projected_slip_days_low, projected_slip_days_high, confidence, status, created_at, "
    "subject_type, subject_value"
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


class PostgresForecastDao(ForecastDao):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def insert_forecast(self, record: ForecastRecord) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO risk.forecasts ({_INSERT_COLUMNS}) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    record.forecast_id, record.project_key, record.requested_by,
                    record.status, record.on_time_probability,
                    record.probability_low, record.probability_high,
                    record.projected_slip_days_low, record.projected_slip_days_high,
                    record.outlook,
                    json.dumps([d.model_dump() for d in record.drivers]),
                    record.bull_case, record.bear_case, record.would_change_mind,
                    record.narrative, record.confidence,
                    record.run_id, record.created_at,
                    record.subject_type, record.subject_value,
                ),
            )

    def list_forecasts(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> ForecastsPageResponse:
        where, params = _scope_clause(scope, q, projects)
        eff_offset = max(0, min(offset, HISTORY_CAP))
        eff_limit = max(0, min(limit, HISTORY_CAP))
        if eff_offset + eff_limit > HISTORY_CAP:
            eff_limit = HISTORY_CAP - eff_offset

        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT LEAST(count(*), {HISTORY_CAP}) FROM risk.forecasts{where}",
                tuple(params),
            )
            total = int(cur.fetchone()[0])
            rows = []
            if eff_limit > 0:
                cur.execute(
                    f"SELECT {_SUMMARY_COLUMNS} FROM risk.forecasts{where} "
                    "ORDER BY created_at DESC, forecast_id LIMIT %s OFFSET %s",
                    tuple(params) + (eff_limit, eff_offset),
                )
                rows = cur.fetchall()
        items = [_to_summary(r) for r in rows]
        return ForecastsPageResponse(
            total=total, returned=len(items), offset=offset, limit=limit, items=items
        )

    def get_forecast(self, forecast_id: str) -> ForecastResponse | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_FULL_COLUMNS} FROM risk.forecasts WHERE forecast_id = %s",
                (forecast_id,),
            )
            row = cur.fetchone()
        return _to_response(row) if row is not None else None


def _to_summary(r: tuple) -> ForecastSummary:
    return ForecastSummary(
        forecast_id=str(r[0]), project_key=r[1],
        on_time_probability=float(r[2]) if r[2] is not None else None,
        outlook=r[3],
        projected_slip_days_low=int(r[4]) if r[4] is not None else None,
        projected_slip_days_high=int(r[5]) if r[5] is not None else None,
        confidence=float(r[6]) if r[6] is not None else None,
        status=r[7], created_at=r[8],
        subject_type=r[9] or "project", subject_value=r[10],
    )


def _to_response(r: tuple) -> ForecastResponse:
    # Column order mirrors _INSERT_COLUMNS. r[2] is requested_by (not surfaced).
    return ForecastResponse(
        forecast_id=str(r[0]), project_key=r[1],
        status=r[3],
        on_time_probability=float(r[4]) if r[4] is not None else 0.0,
        probability_low=float(r[5]) if r[5] is not None else 0.0,
        probability_high=float(r[6]) if r[6] is not None else 0.0,
        projected_slip_days_low=int(r[7]) if r[7] is not None else 0,
        projected_slip_days_high=int(r[8]) if r[8] is not None else 0,
        outlook=r[9] or "",
        drivers=[ForecastDriver(**d) for d in _jsonlist(r[10])],
        bull_case=r[11] or "", bear_case=r[12] or "", would_change_mind=r[13] or "",
        narrative=r[14] or "",
        confidence=float(r[15]) if r[15] is not None else 0.0,
        run_id=r[16], created_at=r[17],
        subject_type=r[18] or "project", subject_value=r[19],
    )
