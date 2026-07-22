"""MongoDB-backed portfolio-summary DAO (read-only).

Joins every project that has a computed-metrics doc with its latest snapshot and
rolls up portfolio-wide totals. Both the join (latest-per-project) and the
totals are done **server-side** with aggregation pipelines so only the compact
scored rows travel back — this is what lets the ranking scale to thousands of
projects while the API returns just the top N.
"""
from __future__ import annotations

from datetime import date

from projects_api.common.utilities import end_of_day_utc
from projects_api.daos.connection import Database
from projects_api.dtos.common import PortfolioAggregate, PortfolioScoredRow
from projects_api.interfaces.daos import PortfolioSummaryDao

# Latest metrics per project (newest computed_at wins), joined to the project's
# name/category/counts. Projects with no metrics doc simply drop out -> unscored.
_SCORED_PIPELINE = [
    {"$sort": {"computed_at": -1}},
    {"$group": {
        "_id": "$project_key",
        "reopen_rate": {"$first": "$reopen_rate"},
        "blocker_count": {"$first": "$blocker_count"},
        "issue_aging_days": {"$first": "$issue_aging_days"},
        "critical_defect_ratio": {"$first": "$critical_defect_ratio"},
    }},
    {"$lookup": {
        "from": "projects", "localField": "_id",
        "foreignField": "project_key", "as": "project",
    }},
    {"$unwind": "$project"},
    {"$project": {
        "_id": 0,
        "project_key": "$_id",
        "name": "$project.name",
        "category": "$project.category",
        "issue_count": "$project.issue_count",
        "open_issue_count": "$project.open_issue_count",
        "reopen_rate": 1,
        "blocker_count": 1,
        "issue_aging_days": 1,
        "critical_defect_ratio": 1,
    }},
]

# Portfolio-wide roll-up: project count + summed issue/open-issue counts.
_TOTALS_PIPELINE = [
    {"$group": {
        "_id": None,
        "projects": {"$sum": 1},
        "issues": {"$sum": {"$ifNull": ["$issue_count", 0]}},
        "open_issues": {"$sum": {"$ifNull": ["$open_issue_count", 0]}},
    }},
]


def _to_row(doc: dict) -> PortfolioScoredRow:
    return PortfolioScoredRow(
        project_key=doc["project_key"],
        name=doc.get("name") or doc["project_key"],
        category=doc.get("category"),
        issue_count=doc.get("issue_count", 0) or 0,
        open_issue_count=doc.get("open_issue_count", 0) or 0,
        blocker_count=doc.get("blocker_count", 0) or 0,
        reopen_rate=doc.get("reopen_rate", 0.0) or 0.0,
        issue_aging_days=doc.get("issue_aging_days", 0.0) or 0.0,
        critical_defect_ratio=doc.get("critical_defect_ratio", 0.0) or 0.0,
    )


class MongoPortfolioSummaryDao(PortfolioSummaryDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def portfolio_data(
        self,
        project_keys: list[str] | None = None,
        as_of: date | None = None,
    ) -> PortfolioAggregate:
        db = self._db.db()
        # Per-user scoping: narrow BOTH pipelines to the caller's project_keys in
        # the DB (prepended $match), so scoping never scans the whole portfolio.
        scope_match = (
            [{"$match": {"project_key": {"$in": project_keys}}}]
            if project_keys is not None
            else []
        )
        # As-of filter (DB-side): keep only snapshots taken on/before the chosen
        # date BEFORE the latest-per-project $sort/$group, so each project's
        # scored row is its latest snapshot as of that date. Totals come from the
        # `projects` collection (no computed_at), so this filter applies only to
        # the metrics pipeline; projects with no qualifying snapshot become
        # unscored.
        as_of_match = (
            [{"$match": {"computed_at": {"$lt": end_of_day_utc(as_of)}}}]
            if as_of is not None
            else []
        )
        scored = [
            _to_row(d)
            for d in db["project_metrics"].aggregate(
                scope_match + as_of_match + _SCORED_PIPELINE
            )
        ]
        totals = next(iter(db["projects"].aggregate(scope_match + _TOTALS_PIPELINE)), None)
        return PortfolioAggregate(
            total_projects=(totals or {}).get("projects", 0),
            total_issues=(totals or {}).get("issues", 0),
            total_open_issues=(totals or {}).get("open_issues", 0),
            scored=scored,
        )
