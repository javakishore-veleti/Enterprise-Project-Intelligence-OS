"""A tiny behavioural fake for the ``PostgresDatabase`` surface the DAOs use.

It is *not* a general SQL engine: it understands exactly the query shapes the
``PostgresInvestigationDao`` issues against ``risk.investigations`` (insert,
capped-count, newest-first summary page with scope/ILIKE filtering + limit/offset,
and fetch-by-id) and applies them against an in-memory row store. That lets the
DAO tests assert real behaviour — scope filter, case-insensitive search, the
100-row cap, DESC ordering, and pagination — with no real database.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

# Positional column order the DAO inserts / selects (mirrors the DAO constants).
_INSERT_COLUMNS = [
    "investigation_id", "project_key", "requested_by", "question", "template_key",
    "status", "root_cause", "confidence", "recommended_action", "hypotheses",
    "causal_chain", "steps", "evidence", "run_id", "created_at",
]
_SUMMARY_COLUMNS = [
    "investigation_id", "project_key", "question", "template_key", "status",
    "root_cause", "confidence", "created_at",
]


def _matches(
    row: dict, scope: str | None, term: str | None, projects: list | None = None
) -> bool:
    if scope is not None and row.get("requested_by") != scope:
        return False
    if term is not None:
        needle = term.strip("%").lower()
        haystacks = [row.get("project_key") or "", row.get("question") or "",
                     row.get("root_cause") or ""]
        if not any(needle in h.lower() for h in haystacks):
            return False
    if projects is not None and row.get("project_key") not in set(projects):
        return False
    return True


class _FakeCursor:
    def __init__(self, db: "FakePostgresDatabase") -> None:
        self._db = db
        self._result: list[tuple] = []

    def execute(self, sql: str, params: tuple | list = ()) -> None:
        self._db.executed.append((sql, tuple(params)))
        low = sql.lower()
        params = list(params)

        if low.startswith("insert into risk.investigations"):
            self._db.rows.append(dict(zip(_INSERT_COLUMNS, params)))
            self._result = []
            return

        # Consume the WHERE params (scope, 3x ILIKE, projects) in the DAO's order.
        idx = 0
        scope = None
        term = None
        projects = None
        if "requested_by = %s" in low:
            scope = params[idx]
            idx += 1
        if "ilike" in low:
            term = params[idx]
            idx += 3  # three placeholders, same value
        if "= any(%s)" in low:
            projects = params[idx]
            idx += 1

        filtered = [r for r in self._db.rows if _matches(r, scope, term, projects)]

        if "least(count(*)" in low:
            self._result = [(min(len(filtered), 100),)]
            return

        if "where investigation_id = %s" in low:
            inv_id = params[0]
            self._result = [
                tuple(r.get(c) for c in _INSERT_COLUMNS)
                for r in self._db.rows if r.get("investigation_id") == inv_id
            ]
            return

        # Summary page: newest-first, tie-break by id, then LIMIT/OFFSET.
        limit, offset = params[idx], params[idx + 1]
        ordered = sorted(
            filtered,
            key=lambda r: (r.get("created_at"), r.get("investigation_id")),
            reverse=True,
        )
        page = ordered[offset:offset + limit]
        self._result = [tuple(r.get(c) for c in _SUMMARY_COLUMNS) for r in page]

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)


class _FakeConn:
    def __init__(self, db: "FakePostgresDatabase") -> None:
        self._db = db

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._db)

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class FakePostgresDatabase:
    """Drop-in for ``PostgresDatabase`` with a shared in-memory row store."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows: list[dict] = list(rows or [])
        self.executed: list[tuple[str, tuple]] = []

    @contextmanager
    def connection(self) -> Iterator[_FakeConn]:
        yield _FakeConn(self)
