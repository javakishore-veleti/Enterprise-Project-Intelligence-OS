"""A behavioural fake for the ``PostgresDatabase`` surface the decision DAO uses.

Like ``pg_predict`` but for ``risk.decisions``, which — unlike the forecast/scenario
tables — is MUTATED after creation (select + approve). So this fake understands the
DAO's query shapes: insert, two UPDATE forms (select / approve), capped-count,
newest-first summary page with scope/ILIKE filtering + limit/offset, and
fetch-by-id — over an in-memory row store. Lets the DAO tests assert real
behaviour (scope, case-insensitive search, the 100-row cap, DESC ordering,
pagination, uuid->str, and the state transitions) with no DB.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

_INSERT_COLUMNS = [
    "decision_id", "project_key", "requested_by", "status", "options",
    "selected_option_id", "narrative", "confidence", "run_id", "created_at",
    "approved_at",
]
_SUMMARY_COLUMNS = [
    "decision_id", "project_key", "status", "selected_option_id", "confidence",
    "options", "created_at",
]
_SEARCH_COLUMNS = ["project_key", "narrative"]


def _matches(
    row: dict, scope: str | None, term: str | None, projects: list | None = None
) -> bool:
    if scope is not None and row.get("requested_by") != scope:
        return False
    if term is not None:
        needle = term.strip("%").lower()
        if not any(needle in str(row.get(c) or "").lower() for c in _SEARCH_COLUMNS):
            return False
    if projects is not None and row.get("project_key") not in set(projects):
        return False
    return True


class _FakeCursor:
    def __init__(self, db: "FakeDecisionDatabase") -> None:
        self._db = db
        self._result: list[tuple] = []

    def execute(self, sql: str, params: tuple | list = ()) -> None:
        self._db.executed.append((sql, tuple(params)))
        low = sql.lower()
        params = list(params)
        db = self._db

        if low.startswith("insert into risk.decisions"):
            db.rows.append(dict(zip(_INSERT_COLUMNS, params)))
            self._result = []
            return

        if low.startswith("update risk.decisions"):
            decision_id = params[-1]
            row = next((r for r in db.rows if r.get("decision_id") == decision_id), None)
            if row is not None:
                if "selected_option_id = %s" in low:
                    row["selected_option_id"], row["status"] = params[0], params[1]
                elif "approved_at = %s" in low:
                    row["status"], row["approved_at"] = params[0], params[1]
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
            idx += len(_SEARCH_COLUMNS)  # N placeholders, same value
        if "= any(%s)" in low:
            projects = params[idx]
            idx += 1

        filtered = [r for r in db.rows if _matches(r, scope, term, projects)]

        if "least(count(*)" in low:
            self._result = [(min(len(filtered), 100),)]
            return

        if "where decision_id = %s" in low:
            key = params[0]
            self._result = [
                tuple(r.get(c) for c in _INSERT_COLUMNS)
                for r in db.rows if r.get("decision_id") == key
            ]
            return

        limit, offset = params[idx], params[idx + 1]
        ordered = sorted(
            filtered,
            key=lambda r: (r.get("created_at"), r.get("decision_id")),
            reverse=True,
        )
        page = ordered[offset:offset + limit]
        self._result = [tuple(r.get(c) for c in _SUMMARY_COLUMNS) for r in page]

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)


class _FakeConn:
    def __init__(self, db: "FakeDecisionDatabase") -> None:
        self._db = db

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._db)

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class FakeDecisionDatabase:
    """``PostgresDatabase`` stand-in for the mutable ``risk.decisions`` table."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows: list[dict] = list(rows or [])
        self.executed: list[tuple[str, tuple]] = []

    @contextmanager
    def connection(self) -> Iterator[_FakeConn]:
        yield _FakeConn(self)


def fake_decision_db(rows: list[dict] | None = None) -> FakeDecisionDatabase:
    return FakeDecisionDatabase(rows=rows)
