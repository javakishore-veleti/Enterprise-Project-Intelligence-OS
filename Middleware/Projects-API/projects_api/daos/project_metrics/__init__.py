"""MongoDB-backed implementation of the project-metrics DAO (read-only)."""
from __future__ import annotations

from pymongo import DESCENDING

from projects_api.daos.connection import Database
from projects_api.dtos.responses import ProjectMetricsResponse
from projects_api.interfaces.daos import ProjectMetricsDao


class MongoProjectMetricsDao(ProjectMetricsDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def latest(self, project_key: str) -> ProjectMetricsResponse | None:
        doc = self._db.db()["project_metrics"].find_one(
            {"project_key": project_key},
            sort=[("computed_at", DESCENDING)],
        )
        if not doc:
            return None
        return ProjectMetricsResponse(
            project_key=doc["project_key"],
            computed_at=doc["computed_at"],
            backlog_growth=doc.get("backlog_growth", 0.0),
            reopen_rate=doc.get("reopen_rate", 0.0),
            blocker_count=doc.get("blocker_count", 0),
            dependency_depth=doc.get("dependency_depth", 0),
        )
