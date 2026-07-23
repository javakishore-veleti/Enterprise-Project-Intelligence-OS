"""MongoDB-backed implementation of the projects DAO (read-only)."""
from __future__ import annotations

import re

from projects_api.daos.connection import Database
from projects_api.dtos.common import ProjectSearchScoredRow
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

# Left-join each matched project to its latest metrics snapshot (newest
# computed_at wins) so the service can rank by the composite risk_score.
_LATEST_METRICS_LOOKUP = {
    "$lookup": {
        "from": "project_metrics",
        "let": {"pk": "$project_key"},
        "pipeline": [
            {"$match": {"$expr": {"$eq": ["$project_key", "$$pk"]}}},
            {"$sort": {"computed_at": -1}},
            {"$limit": 1},
            {"$project": {
                "_id": 0,
                "reopen_rate": 1,
                "blocker_count": 1,
                "issue_aging_days": 1,
                "critical_defect_ratio": 1,
            }},
        ],
        "as": "metrics",
    }
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

    def search_scored(self, query, project_keys):
        match = self._filter(query)
        if project_keys is not None:
            # Narrow to the caller's assigned projects in the DB (per-user scope).
            match = {**match, "project_key": {"$in": project_keys}}
        pipeline = [
            {"$match": match},
            _LATEST_METRICS_LOOKUP,
            {"$project": {
                "_id": 0,
                "project_key": 1,
                "name": 1,
                "issue_count": 1,
                "open_issue_count": 1,
                "metrics": {"$arrayElemAt": ["$metrics", 0]},
            }},
        ]
        rows: list[ProjectSearchScoredRow] = []
        for doc in self._collection().aggregate(pipeline):
            metrics = doc.get("metrics")
            rows.append(ProjectSearchScoredRow(
                project_key=doc["project_key"],
                name=doc.get("name") or doc["project_key"],
                open_issue_count=doc.get("open_issue_count", 0) or 0,
                issue_count=doc.get("issue_count", 0) or 0,
                has_metrics=metrics is not None,
                blocker_count=(metrics or {}).get("blocker_count", 0) or 0,
                reopen_rate=(metrics or {}).get("reopen_rate", 0.0) or 0.0,
                issue_aging_days=(metrics or {}).get("issue_aging_days", 0.0) or 0.0,
                critical_defect_ratio=(metrics or {}).get("critical_defect_ratio", 0.0) or 0.0,
            ))
        return rows

    def get(self, project_key):
        doc = self._collection().find_one({"project_key": project_key}, _PROJECTION)
        return _doc_to_response(doc) if doc else None
