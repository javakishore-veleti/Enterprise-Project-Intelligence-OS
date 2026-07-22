"""MongoDB-backed implementation of the project-groups DAO (read/write).

Stores user-defined project groups in the ``project_groups`` collection with a
unique index on ``group_key`` (created defensively).
"""
from __future__ import annotations

from pymongo import DESCENDING

from projects_api.daos.connection import Database
from projects_api.dtos.responses import ProjectGroupResponse
from projects_api.interfaces.daos import ProjectGroupsDao

_PROJECTION = {"_id": 0}


def _doc_to_response(doc: dict) -> ProjectGroupResponse:
    return ProjectGroupResponse(
        group_key=doc["group_key"],
        name=doc.get("name", doc["group_key"]),
        description=doc.get("description", ""),
        project_keys=list(doc.get("project_keys", [])),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _response_to_doc(record: ProjectGroupResponse) -> dict:
    return {
        "group_key": record.group_key,
        "name": record.name,
        "description": record.description,
        "project_keys": list(record.project_keys),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


class MongoProjectGroupsDao(ProjectGroupsDao):
    def __init__(self, database: Database) -> None:
        self._db = database
        self._index_ready = False

    def _collection(self):
        coll = self._db.db()["project_groups"]
        if not self._index_ready:
            # Idempotent; keeps group_key unique even under concurrent writers.
            coll.create_index("group_key", unique=True)
            self._index_ready = True
        return coll

    def list_all(self) -> list[ProjectGroupResponse]:
        cursor = self._collection().find({}, _PROJECTION).sort("created_at", DESCENDING)
        return [_doc_to_response(d) for d in cursor]

    def get(self, group_key: str) -> ProjectGroupResponse | None:
        doc = self._collection().find_one({"group_key": group_key}, _PROJECTION)
        return _doc_to_response(doc) if doc else None

    def insert(self, record: ProjectGroupResponse) -> ProjectGroupResponse:
        self._collection().insert_one(_response_to_doc(record))
        return record

    def replace(self, record: ProjectGroupResponse) -> ProjectGroupResponse:
        self._collection().replace_one(
            {"group_key": record.group_key}, _response_to_doc(record))
        return record

    def delete(self, group_key: str) -> bool:
        return self._collection().delete_one({"group_key": group_key}).deleted_count > 0
