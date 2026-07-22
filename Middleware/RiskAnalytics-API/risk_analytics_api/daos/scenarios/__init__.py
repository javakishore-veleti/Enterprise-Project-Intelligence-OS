"""PostgreSQL-backed persistence of digital-twin scenario runs.

Structurally identical to ``daos/investigations``: newest-first history capped at
the most recent 100 rows, scope (``requested_by``) + case-insensitive ``q``
(project_key/scenario/narrative ILIKE ``%q%``) filtered in SQL, uuid PK cast to
``str`` in the row mappers.
"""
from __future__ import annotations

import json

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.responses import (
    ScenarioCascade,
    ScenarioRecord,
    ScenarioResponse,
    ScenarioSummary,
    ScenariosPageResponse,
)
from risk_analytics_api.interfaces.daos import ScenarioDao

#: Hard ceiling on the history: the list + total never exceed this.
HISTORY_CAP = 100

_INSERT_COLUMNS = (
    "scenario_id, project_key, requested_by, scenario, status, "
    "base_on_time_probability, projected_on_time_probability, probability_delta, "
    "base_slip_days, projected_slip_days, portfolio_risk_delta, cascades, "
    "narrative, confidence, run_id, created_at"
)
_FULL_COLUMNS = _INSERT_COLUMNS
_SUMMARY_COLUMNS = (
    "scenario_id, project_key, scenario, projected_on_time_probability, "
    "probability_delta, confidence, status, created_at"
)


def _jsonlist(v) -> list:
    if isinstance(v, str):
        v = json.loads(v)
    return list(v or [])


def _scope_clause(scope: str | None, q: str | None) -> tuple[str, list]:
    """Build a parameterised WHERE clause for scope + case-insensitive search."""
    clauses: list[str] = []
    params: list = []
    if scope:
        clauses.append("requested_by = %s")
        params.append(scope)
    if q:
        clauses.append("(project_key ILIKE %s OR scenario ILIKE %s OR narrative ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


class PostgresScenarioDao(ScenarioDao):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def insert_scenario(self, record: ScenarioRecord) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO risk.scenarios ({_INSERT_COLUMNS}) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
                (
                    record.scenario_id, record.project_key, record.requested_by,
                    record.scenario, record.status,
                    record.base_on_time_probability, record.projected_on_time_probability,
                    record.probability_delta, record.base_slip_days,
                    record.projected_slip_days, record.portfolio_risk_delta,
                    json.dumps([c.model_dump() for c in record.cascades]),
                    record.narrative, record.confidence, record.run_id, record.created_at,
                ),
            )

    def list_scenarios(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> ScenariosPageResponse:
        where, params = _scope_clause(scope, q)
        eff_offset = max(0, min(offset, HISTORY_CAP))
        eff_limit = max(0, min(limit, HISTORY_CAP))
        if eff_offset + eff_limit > HISTORY_CAP:
            eff_limit = HISTORY_CAP - eff_offset

        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT LEAST(count(*), {HISTORY_CAP}) FROM risk.scenarios{where}",
                tuple(params),
            )
            total = int(cur.fetchone()[0])
            rows = []
            if eff_limit > 0:
                cur.execute(
                    f"SELECT {_SUMMARY_COLUMNS} FROM risk.scenarios{where} "
                    "ORDER BY created_at DESC, scenario_id LIMIT %s OFFSET %s",
                    tuple(params) + (eff_limit, eff_offset),
                )
                rows = cur.fetchall()
        items = [_to_summary(r) for r in rows]
        return ScenariosPageResponse(
            total=total, returned=len(items), offset=offset, limit=limit, items=items
        )

    def get_scenario(self, scenario_id: str) -> ScenarioResponse | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_FULL_COLUMNS} FROM risk.scenarios WHERE scenario_id = %s",
                (scenario_id,),
            )
            row = cur.fetchone()
        return _to_response(row) if row is not None else None


def _to_summary(r: tuple) -> ScenarioSummary:
    return ScenarioSummary(
        scenario_id=str(r[0]), project_key=r[1], scenario=r[2],
        projected_on_time_probability=float(r[3]) if r[3] is not None else None,
        probability_delta=float(r[4]) if r[4] is not None else None,
        confidence=float(r[5]) if r[5] is not None else None,
        status=r[6], created_at=r[7],
    )


def _to_response(r: tuple) -> ScenarioResponse:
    # Column order mirrors _INSERT_COLUMNS. r[2] is requested_by (not surfaced).
    return ScenarioResponse(
        scenario_id=str(r[0]), project_key=r[1], scenario=r[3],
        status=r[4],
        base_on_time_probability=float(r[5]) if r[5] is not None else 0.0,
        projected_on_time_probability=float(r[6]) if r[6] is not None else 0.0,
        probability_delta=float(r[7]) if r[7] is not None else 0.0,
        base_slip_days=int(r[8]) if r[8] is not None else 0,
        projected_slip_days=int(r[9]) if r[9] is not None else 0,
        portfolio_risk_delta=float(r[10]) if r[10] is not None else 0.0,
        cascades=[ScenarioCascade(**c) for c in _jsonlist(r[11])],
        narrative=r[12] or "",
        confidence=float(r[13]) if r[13] is not None else 0.0,
        run_id=r[14], created_at=r[15],
    )
