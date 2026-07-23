"""A parametric behavioural fake for the ``PostgresDatabase`` surface the Predict
DAOs use (forecasts + scenarios).

Not a general SQL engine: it understands exactly the query shapes the
``PostgresForecastDao`` / ``PostgresScenarioDao`` issue (insert, capped-count,
newest-first summary page with scope/ILIKE filtering + limit/offset, fetch-by-id)
against an in-memory row store — parametrized by table name + column lists so the
one fake serves both tables. Lets the DAO tests assert real behaviour (scope,
case-insensitive search, the 100-row cap, DESC ordering, pagination) with no DB.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


def _matches(
    row: dict, scope: str | None, term: str | None, search_cols: list[str],
    projects: list | None = None,
) -> bool:
    if scope is not None and row.get("requested_by") != scope:
        return False
    if term is not None:
        needle = term.strip("%").lower()
        if not any(needle in str(row.get(c) or "").lower() for c in search_cols):
            return False
    if projects is not None and row.get("project_key") not in set(projects):
        return False
    return True


class _FakeCursor:
    def __init__(self, db: "FakePredictDatabase") -> None:
        self._db = db
        self._result: list[tuple] = []

    def execute(self, sql: str, params: tuple | list = ()) -> None:
        self._db.executed.append((sql, tuple(params)))
        low = sql.lower()
        params = list(params)
        db = self._db

        if low.startswith(f"insert into {db.table}"):
            db.rows.append(dict(zip(db.insert_columns, params)))
            self._result = []
            return

        idx = 0
        scope = None
        term = None
        projects = None
        if "requested_by = %s" in low:
            scope = params[idx]
            idx += 1
        if "ilike" in low:
            term = params[idx]
            idx += len(db.search_columns)  # N placeholders, same value
        if "= any(%s)" in low:
            projects = params[idx]
            idx += 1

        filtered = [
            r for r in db.rows
            if _matches(r, scope, term, db.search_columns, projects)
        ]

        if "least(count(*)" in low:
            self._result = [(min(len(filtered), 100),)]
            return

        if f"where {db.id_column} = %s" in low:
            key = params[0]
            self._result = [
                tuple(r.get(c) for c in db.insert_columns)
                for r in db.rows if r.get(db.id_column) == key
            ]
            return

        limit, offset = params[idx], params[idx + 1]
        ordered = sorted(
            filtered,
            key=lambda r: (r.get("created_at"), r.get(db.id_column)),
            reverse=True,
        )
        page = ordered[offset:offset + limit]
        self._result = [tuple(r.get(c) for c in db.summary_columns) for r in page]

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)


class _FakeConn:
    def __init__(self, db: "FakePredictDatabase") -> None:
        self._db = db

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._db)

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class FakePredictDatabase:
    """Parametric ``PostgresDatabase`` stand-in for one Predict table."""

    def __init__(
        self, table: str, id_column: str,
        insert_columns: list[str], summary_columns: list[str], search_columns: list[str],
        rows: list[dict] | None = None,
    ) -> None:
        self.table = table
        self.id_column = id_column
        self.insert_columns = insert_columns
        self.summary_columns = summary_columns
        self.search_columns = search_columns
        self.rows: list[dict] = list(rows or [])
        self.executed: list[tuple[str, tuple]] = []

    @contextmanager
    def connection(self) -> Iterator[_FakeConn]:
        yield _FakeConn(self)


_FORECAST_INSERT = [
    "forecast_id", "project_key", "requested_by", "status", "on_time_probability",
    "probability_low", "probability_high", "projected_slip_days_low",
    "projected_slip_days_high", "outlook", "drivers", "bull_case", "bear_case",
    "would_change_mind", "narrative", "confidence", "run_id", "created_at",
    "subject_type", "subject_value",
]
_FORECAST_SUMMARY = [
    "forecast_id", "project_key", "on_time_probability", "outlook",
    "projected_slip_days_low", "projected_slip_days_high", "confidence",
    "status", "created_at", "subject_type", "subject_value",
]

_SCENARIO_INSERT = [
    "scenario_id", "project_key", "requested_by", "scenario", "status",
    "base_on_time_probability", "projected_on_time_probability", "probability_delta",
    "base_slip_days", "projected_slip_days", "portfolio_risk_delta", "cascades",
    "narrative", "confidence", "run_id", "created_at",
]
_SCENARIO_SUMMARY = [
    "scenario_id", "project_key", "scenario", "projected_on_time_probability",
    "probability_delta", "confidence", "status", "created_at",
]


def fake_forecast_db(rows: list[dict] | None = None) -> FakePredictDatabase:
    return FakePredictDatabase(
        table="risk.forecasts", id_column="forecast_id",
        insert_columns=_FORECAST_INSERT, summary_columns=_FORECAST_SUMMARY,
        search_columns=["project_key", "narrative"], rows=rows,
    )


def fake_scenario_db(rows: list[dict] | None = None) -> FakePredictDatabase:
    return FakePredictDatabase(
        table="risk.scenarios", id_column="scenario_id",
        insert_columns=_SCENARIO_INSERT, summary_columns=_SCENARIO_SUMMARY,
        search_columns=["project_key", "scenario", "narrative"], rows=rows,
    )
