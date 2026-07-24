"""PostgreSQL-backed persistence of the organization tree.

Materialized path: `path` is dotted ancestor uuids ending in self. Subtree /
ancestor queries are path-prefix scans (backed by the text_pattern_ops index).
Moving a node rewrites the path prefix of the node AND every descendant in a
single UPDATE (Postgres evaluates the WHERE against the pre-update snapshot).
"""
from __future__ import annotations

from org_management_api.common.utilities import escape_like
from org_management_api.daos.connection import Database
from org_management_api.dtos.common import OrganizationPage, OrganizationRecord
from org_management_api.interfaces.daos import OrganizationsDao

_COLUMNS = "org_id, parent_org_id, root_org_id, path, depth, level, name, kind, status, created_at"


def _row(r: tuple) -> OrganizationRecord:
    return OrganizationRecord(
        org_id=str(r[0]),
        parent_org_id=str(r[1]) if r[1] is not None else None,
        root_org_id=str(r[2]),
        path=r[3],
        depth=r[4],
        level=r[5],
        name=r[6],
        kind=r[7],
        status=r[8],
        created_at=r[9],
    )


class PostgresOrganizationsDao(OrganizationsDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    @staticmethod
    def _attach_counts(conn, records: list[OrganizationRecord]) -> list[OrganizationRecord]:
        """Populate child_count + member_count for a page of orgs in two grouped
        queries (never one-per-row). Records are returned unchanged if empty."""
        if not records:
            return records
        ids = [r.org_id for r in records]
        placeholders = ",".join(["%s"] * len(ids))
        cur = conn.cursor()
        cur.execute(
            "SELECT parent_org_id, COUNT(*) FROM org.organizations "
            f"WHERE parent_org_id IN ({placeholders}) GROUP BY parent_org_id",
            tuple(ids))
        children = {str(row[0]): row[1] for row in cur.fetchall()}
        cur.execute(
            "SELECT org_id, COUNT(*) FROM org.memberships "
            f"WHERE org_id IN ({placeholders}) GROUP BY org_id",
            tuple(ids))
        members = {str(row[0]): row[1] for row in cur.fetchall()}
        return [
            r.model_copy(update={
                "child_count": children.get(r.org_id, 0),
                "member_count": members.get(r.org_id, 0),
            })
            for r in records
        ]

    def insert(self, record: OrganizationRecord) -> OrganizationRecord:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO org.organizations ({_COLUMNS}) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                f"RETURNING {_COLUMNS}",
                (
                    record.org_id, record.parent_org_id, record.root_org_id, record.path,
                    record.depth, record.level, record.name, record.kind, record.status,
                    record.created_at,
                ),
            )
            return _row(cur.fetchone())

    def get(self, org_id: str) -> OrganizationRecord | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.organizations WHERE org_id = %s", (org_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._attach_counts(conn, [_row(row)])[0]

    # Whitelisted ORDER BY clauses for the children page (never interpolate raw
    # sort input into SQL). `child_count` orders by the number of DIRECT children
    # via a correlated subquery so the "most sub-orgs first" view is exact.
    _CHILD_ORDER = {
        "name": "name, org_id",
        "created_at": "created_at DESC, org_id",
        "child_count": (
            "(SELECT COUNT(*) FROM org.organizations c "
            "WHERE c.parent_org_id = org.organizations.org_id) DESC, name, org_id"
        ),
    }

    def children(
        self,
        org_id: str,
        limit: int = 50,
        offset: int = 0,
        q: str | None = None,
        sort: str = "name",
    ) -> OrganizationPage:
        order_by = self._CHILD_ORDER.get(sort or "name", self._CHILD_ORDER["name"])
        where = "parent_org_id = %s"
        params: list = [org_id]
        if q:
            where += " AND name ILIKE %s ESCAPE '\\'"
            params.append(f"%{escape_like(q)}%")
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM org.organizations WHERE {where}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.organizations "
                f"WHERE {where} ORDER BY {order_by} LIMIT %s OFFSET %s",
                tuple(params) + (limit, offset))
            rows = self._attach_counts(conn, [_row(r) for r in cur.fetchall()])
            return OrganizationPage(organizations=rows, total=total, offset=offset, limit=limit)

    def search(self, q: str, root: str | None, limit: int, offset: int) -> OrganizationPage:
        like = f"%{escape_like(q)}%"
        where = "name ILIKE %s ESCAPE '\\'"
        params: list = [like]
        if root:
            where += " AND root_org_id = %s"
            params.append(root)
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM org.organizations WHERE {where}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.organizations WHERE {where} "
                "ORDER BY name, org_id LIMIT %s OFFSET %s",
                tuple(params) + (limit, offset))
            rows = self._attach_counts(conn, [_row(r) for r in cur.fetchall()])
            return OrganizationPage(organizations=rows, total=total, offset=offset, limit=limit)

    def subtree(self, path: str) -> list[OrganizationRecord]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.organizations "
                "WHERE path = %s OR path LIKE %s ORDER BY path",
                (path, f"{path}.%"))
            return [_row(r) for r in cur.fetchall()]

    def ancestors(self, path: str) -> list[OrganizationRecord]:
        # Strict ancestors: orgs whose path is a proper prefix of `path`.
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.organizations "
                "WHERE %s LIKE path || '.%' ORDER BY level",
                (path,))
            return [_row(r) for r in cur.fetchall()]

    def update(self, org_id: str, name: str, kind: str | None) -> OrganizationRecord | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE org.organizations SET name = %s, kind = %s "
                f"WHERE org_id = %s RETURNING {_COLUMNS}",
                (name, kind, org_id))
            row = cur.fetchone()
            return _row(row) if row else None

    def list_roots(self) -> list[OrganizationRecord]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.organizations "
                "WHERE parent_org_id IS NULL ORDER BY name, org_id")
            return self._attach_counts(conn, [_row(r) for r in cur.fetchall()])

    def list_by_root(self, root_org_id: str) -> list[OrganizationRecord]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.organizations "
                "WHERE root_org_id = %s ORDER BY path", (root_org_id,))
            return [_row(r) for r in cur.fetchall()]

    def reparent(
        self,
        node_id: str,
        new_parent_id: str,
        old_path: str,
        new_path: str,
        new_root_org_id: str,
        depth_delta: int,
        level_delta: int,
    ) -> None:
        # Rewrite path prefix (old_path -> new_path) for the node and every
        # descendant, shifting depth/level and rehoming root. `substr(path, N)`
        # keeps each row's suffix below old_path (substr, not substring(... from
        # ...), so the integer arg is never mis-resolved as a regex pattern).
        suffix_start = len(old_path) + 1
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE org.organizations "
                "SET path = %s || substr(path, %s), "
                "    depth = depth + %s, "
                "    level = level + %s, "
                "    root_org_id = %s "
                "WHERE path = %s OR path LIKE %s",
                (new_path, suffix_start, depth_delta, level_delta, new_root_org_id,
                 old_path, f"{old_path}.%"))
            cur.execute(
                "UPDATE org.organizations SET parent_org_id = %s WHERE org_id = %s",
                (new_parent_id, node_id))
