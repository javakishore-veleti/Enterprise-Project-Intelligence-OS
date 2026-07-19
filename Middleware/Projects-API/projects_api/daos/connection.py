"""MongoDB connection helper shared by DAOs in this service.

Wraps a process-wide ``MongoClient``. DAOs receive a ``Database`` and ask for
collections, so the driver detail stays confined to this module.
"""
from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase
from pymongo.errors import PyMongoError

from projects_api.common.configuration import Settings
from projects_api.common.exceptions import DependencyUnavailableError


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: MongoClient | None = None

    def _connect(self) -> MongoClient:
        if self._client is None:
            self._client = MongoClient(
                self._settings.mongo_uri,
                serverSelectionTimeoutMS=2000,
            )
        return self._client

    def db(self) -> MongoDatabase:
        return self._connect()[self._settings.mongo_database]

    def ping(self) -> bool:
        """Return True if the server responds; used by readiness checks."""
        try:
            self._connect().admin.command("ping")
        except PyMongoError as exc:
            raise DependencyUnavailableError(f"MongoDB unavailable: {exc}") from exc
        return True
