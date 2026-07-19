"""Database connection helpers shared by DAOs in this service.

This service spans two stores: PostgreSQL (agent config + persisted findings)
and MongoDB (the evidence store). Both driver details are confined here.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pg8000.dbapi
from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase
from pymongo.errors import PyMongoError

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import DependencyUnavailableError


class PostgresDatabase:
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
        except Exception as exc:  # pragma: no cover
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
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        return True


class MongoDatabaseFactory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: MongoClient | None = None

    def _connect(self) -> MongoClient:
        if self._client is None:
            self._client = MongoClient(self._settings.mongo_uri, serverSelectionTimeoutMS=2000)
        return self._client

    def db(self) -> MongoDatabase:
        return self._connect()[self._settings.mongo_database]

    def ping(self) -> bool:
        try:
            self._connect().admin.command("ping")
        except PyMongoError as exc:
            raise DependencyUnavailableError(f"MongoDB unavailable: {exc}") from exc
        return True
