"""MongoDB-backed implementation of the projects DAO (read-only)."""
from __future__ import annotations

import re

from projects_api.daos.connection import Database
from projects_api.dtos.responses import ProjectResponse
from projects_api.interfaces.daos import ProjectsDao

_PROJECTION = {
    "_id": 0,
    "project_key": 1,
    "name": 1,
    "category": 1,
    "issue_count": 1,
    "open_issue_count": 1,
}


def _doc_to_response(doc: dict) -> ProjectResponse:
    return ProjectResponse(
        project_key=doc["project_key"],
        name=doc.get("name", doc["project_key"]),
        category=doc.get("category"),
        issue_count=doc.get("issue_count", 0),
        open_issue_count=doc.get("open_issue_count", 0),
    )


class MongoProjectsDao(ProjectsDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def _collection(self):
        return self._db.db()["projects"]

    def _filter(self, query: str | None) -> dict:
        if not query:
            return {}
        rx = {"$regex": re.escape(query), "$options": "i"}
        return {"$or": [{"project_key": rx}, {"name": rx}]}

    def search(self, query, limit, offset):
        coll = self._collection()
        flt = self._filter(query)
        total = coll.count_documents(flt)
        cursor = (
            coll.find(flt, _PROJECTION)
            .sort("project_key", 1)
            .skip(offset)
            .limit(limit)
        )
        return [_doc_to_response(d) for d in cursor], total

    def get(self, project_key):
        doc = self._collection().find_one({"project_key": project_key}, _PROJECTION)
        return _doc_to_response(doc) if doc else None
