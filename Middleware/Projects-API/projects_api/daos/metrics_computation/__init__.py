"""MongoDB reads of raw evidence + writes of computed metrics.

Assumed evidence schema (tune once the real archive layout is known):
- issues:          {issue_key, project_key, status, priority, created_at, resolved_at}
- issue_histories: {issue_key, project_key, field, to_value, changed_at}
- issue_links:     {source_issue_key, target_issue_key, link_type, project_key}
Open = status not in CLOSED_STATES.
"""
from __future__ import annotations

from projects_api.daos.connection import Database
from projects_api.interfaces.daos import MetricsComputationDao

CLOSED_STATES = ["Resolved", "Closed", "Done"]
BLOCKING_LINKS = ["blocks", "is blocked by", "depends on", "Blocks", "Depends"]
REOPEN_VALUES = ["Reopened", "Open", "Reopen"]
CRITICAL_PRIORITIES = ["Blocker", "Critical"]


class MongoMetricsComputationDao(MetricsComputationDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def _c(self, name: str):
        return self._db.db()[name]

    def list_project_keys(self, limit: int) -> list[str]:
        return [k for k in self._c("projects").distinct("project_key")][:limit]

    def counts(self, project_key: str) -> dict:
        issues = self._c("issues")
        total = issues.count_documents({"project_key": project_key})
        resolved = issues.count_documents({"project_key": project_key, "status": {"$in": CLOSED_STATES}})
        open_count = total - resolved
        blockers = issues.count_documents({
            "project_key": project_key, "priority": "Blocker",
            "status": {"$nin": CLOSED_STATES},
        })
        return {"issue_count": total, "open_issue_count": open_count,
                "resolved_count": resolved, "blocker_count": blockers}

    def reopened_count(self, project_key: str) -> int:
        keys = self._c("issue_histories").distinct("issue_key", {
            "project_key": project_key, "field": "status", "to_value": {"$in": REOPEN_VALUES}})
        return len(keys)

    def reference_date(self, project_key: str):
        doc = self._c("issues").find_one(
            {"project_key": project_key, "created_at": {"$ne": None}},
            {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
        return doc["created_at"] if doc else None

    def created_between(self, project_key: str, start, end) -> int:
        return self._c("issues").count_documents(
            {"project_key": project_key, "created_at": {"$gte": start, "$lte": end}})

    def resolved_between(self, project_key: str, start, end) -> int:
        return self._c("issues").count_documents(
            {"project_key": project_key, "resolved_at": {"$gte": start, "$lte": end}})

    def blocking_links(self, project_key: str) -> list[tuple[str, str]]:
        cursor = self._c("issue_links").find(
            {"project_key": project_key, "link_type": {"$in": BLOCKING_LINKS}},
            {"_id": 0, "source_issue_key": 1, "target_issue_key": 1})
        return [(d["source_issue_key"], d["target_issue_key"])
                for d in cursor if d.get("source_issue_key") and d.get("target_issue_key")]

    def avg_open_age_days(self, project_key: str, reference) -> float:
        cursor = self._c("issues").find(
            {"project_key": project_key, "status": {"$nin": CLOSED_STATES},
             "created_at": {"$ne": None}},
            {"_id": 0, "created_at": 1})
        ages = []
        for d in cursor:
            created = d.get("created_at")
            if created is not None:
                ages.append((reference - created).total_seconds() / 86400.0)
        return round(sum(ages) / len(ages), 1) if ages else 0.0

    def top_contributor_share(self, project_key: str) -> float:
        counts: dict[str, int] = {}
        for coll, field in (("comments", "author"), ("issue_histories", "author")):
            for d in self._c(coll).find({"project_key": project_key}, {"_id": 0, field: 1}):
                author = d.get(field)
                if author:
                    counts[author] = counts.get(author, 0) + 1
        total = sum(counts.values())
        return round(max(counts.values()) / total, 3) if total else 0.0

    def critical_open_count(self, project_key: str) -> int:
        return self._c("issues").count_documents({
            "project_key": project_key, "status": {"$nin": CLOSED_STATES},
            "priority": {"$in": CRITICAL_PRIORITIES}})

    def write_metrics(self, project_key: str, metrics: dict, computed_at) -> None:
        self._c("project_metrics").update_one(
            {"project_key": project_key, "computed_at": computed_at},
            {"$set": {"project_key": project_key, "computed_at": computed_at, **metrics}},
            upsert=True)

    def update_project_counts(self, project_key: str, issue_count: int, open_issue_count: int) -> None:
        self._c("projects").update_one(
            {"project_key": project_key},
            {"$set": {"issue_count": issue_count, "open_issue_count": open_issue_count}})
