"""MongoDB-backed project-assignments DAO (read-only, the scoping seam).

Stores per-user project assignments in the ``project_assignments`` collection:
``{ org_id, user_key, project_key, role }`` with ``role`` in owner|manager|member.
A defensive index on ``user_key`` keeps the ``project_keys_for`` lookup indexed
(the design's contract index is ``(org_id, user_key)``; we index ``user_key``
since org resolution is not yet wired — additive when identity/JWT lands).
"""
from __future__ import annotations

from projects_api.daos.connection import Database
from projects_api.interfaces.daos import ProjectAssignmentsDao

_PROJECTION = {"_id": 0, "project_key": 1}


class MongoProjectAssignmentsDao(ProjectAssignmentsDao):
    def __init__(self, database: Database) -> None:
        self._db = database
        self._index_ready = False

    def _collection(self):
        coll = self._db.db()["project_assignments"]
        if not self._index_ready:
            # Idempotent; keeps the per-user scoping lookup indexed.
            coll.create_index("user_key")
            self._index_ready = True
        return coll

    def project_keys_for(self, user_key: str) -> list[str]:
        cursor = self._collection().find({"user_key": user_key}, _PROJECTION)
        # De-dup while preserving a stable order; a user may have >1 role row.
        seen: dict[str, None] = {}
        for doc in cursor:
            key = doc.get("project_key")
            if key:
                seen.setdefault(key, None)
        return list(seen)
