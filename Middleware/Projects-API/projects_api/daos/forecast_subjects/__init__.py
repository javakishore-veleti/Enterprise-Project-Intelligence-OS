"""MongoDB faceting of the forecast-subject arrays on a project's issues.

Reads the three list fields ``transform_issue`` captures (``fix_versions`` /
``components`` / ``labels``) and, per field, unwinds -> groups -> counts ->
sorts the values so the UI can offer the top Release / Component / Tag choices to
scope a forecast to. Pure aggregation in the database (never pulls issues into
Python); missing/absent arrays simply produce empty facet lists.
"""
from __future__ import annotations

from projects_api.daos.connection import Database
from projects_api.dtos.responses import ForecastSubjectFacet, ForecastSubjectsResponse
from projects_api.interfaces.daos import ForecastSubjectsDao

#: Evidence issue array field backing each forecast-subject facet.
_FIELD_BY_FACET = {"releases": "fix_versions", "components": "components", "tags": "labels"}


class MongoForecastSubjectsDao(ForecastSubjectsDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def _facet(self, project_key: str, field: str, cap: int) -> list[ForecastSubjectFacet]:
        pipeline = [
            {"$match": {"project_key": project_key}},
            {"$unwind": f"${field}"},
            {"$match": {field: {"$nin": [None, ""]}}},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$sort": {"count": -1, "_id": 1}},
            {"$limit": cap},
        ]
        return [
            ForecastSubjectFacet(value=doc["_id"], count=int(doc["count"]))
            for doc in self._db.db()["issues"].aggregate(pipeline)
        ]

    def facets(self, project_key: str, cap: int) -> ForecastSubjectsResponse:
        return ForecastSubjectsResponse(
            project_key=project_key,
            releases=self._facet(project_key, _FIELD_BY_FACET["releases"], cap),
            components=self._facet(project_key, _FIELD_BY_FACET["components"], cap),
            tags=self._facet(project_key, _FIELD_BY_FACET["tags"], cap),
        )
