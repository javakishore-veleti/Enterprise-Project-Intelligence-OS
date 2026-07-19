"""Read-only counts from the MongoDB evidence store.

Lets validate/index/reconcile report real numbers against the destination store
without the Ingestion API owning evidence writes.
"""
from __future__ import annotations

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from ingestion_api.common.configuration import Settings
from ingestion_api.common.exceptions import DependencyUnavailableError
from ingestion_api.interfaces.daos import EvidenceCountsGateway

_EVIDENCE_COLLECTIONS = (
    "projects", "issues", "issue_histories", "comments", "issue_links", "project_metrics",
)


class MongoEvidenceCountsGateway(EvidenceCountsGateway):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: MongoClient | None = None

    def _db(self):
        if self._client is None:
            self._client = MongoClient(self._settings.mongo_uri, serverSelectionTimeoutMS=2000)
        return self._client[self._settings.mongo_database]

    def document_count(self) -> int:
        try:
            db = self._db()
            existing = set(db.list_collection_names())
            return sum(
                db[c].estimated_document_count() for c in _EVIDENCE_COLLECTIONS if c in existing
            )
        except PyMongoError as exc:
            raise DependencyUnavailableError(f"MongoDB unavailable: {exc}") from exc

    def index_count(self) -> int:
        try:
            db = self._db()
            existing = set(db.list_collection_names())
            return sum(
                len(list(db[c].list_indexes())) for c in _EVIDENCE_COLLECTIONS if c in existing
            )
        except PyMongoError as exc:
            raise DependencyUnavailableError(f"MongoDB unavailable: {exc}") from exc

    def collection_count(self) -> int:
        try:
            existing = set(self._db().list_collection_names())
            return sum(1 for c in _EVIDENCE_COLLECTIONS if c in existing)
        except PyMongoError as exc:
            raise DependencyUnavailableError(f"MongoDB unavailable: {exc}") from exc
