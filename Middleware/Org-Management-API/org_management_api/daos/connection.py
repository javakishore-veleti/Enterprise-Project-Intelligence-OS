"""PostgreSQL connection helper shared by DAOs in this service.

Uses pg8000 (a pure-Python DB-API driver) so the service installs and runs
without libpq or compiler toolchains. DAOs depend only on the DB-API surface,
so swapping to psycopg later is a change confined to this module.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pg8000.dbapi

from org_management_api.common.configuration import Settings
from org_management_api.common.exceptions import DependencyUnavailableError


class Database:
    """Thin factory that hands out short-lived connections from Settings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @contextmanager
    def connection(self) -> Iterator["pg8000.dbapi.Connection"]:
        try:
            conn = pg8000.dbapi.connect(
                host=self._settings.pg_host,
                port=self._settings.pg_port,
                user=self._settings.pg_user,
                password=self._settings.pg_password,
                database=self._settings.pg_database,
            )
        except Exception as exc:  # pragma: no cover - exercised via readiness
            raise DependencyUnavailableError(f"PostgreSQL unavailable: {exc}") from exc
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ping(self) -> bool:
        """Return True if a trivial query succeeds; used by readiness checks."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
