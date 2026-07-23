"""PostgreSQL-backed persistence of memberships + role assignments.

A user is a *member* of an org (memberships) and separately holds zero-or-more
*roles* there (role_assignments). List queries LEFT JOIN roles onto memberships
and group per member/org in Python.
"""
from __future__ import annotations

from org_management_api.dtos.common import (
    OrganizationRecord,
    RoleAssignmentRecord,
    UserRecord,
)
from org_management_api.interfaces.daos import MembersDao

_USER_COLS = "u.user_id, u.subject, u.email, u.display_name, u.created_at"
_ORG_COLS = (
    "o.org_id, o.parent_org_id, o.root_org_id, o.path, o.depth, o.level, "
    "o.name, o.kind, o.status, o.created_at"
)


def _user(r: tuple) -> UserRecord:
    return UserRecord(
        user_id=str(r[0]), subject=r[1], email=r[2], display_name=r[3], created_at=r[4])


def _org(r: tuple, base: int = 0) -> OrganizationRecord:
    return OrganizationRecord(
        org_id=str(r[base]),
        parent_org_id=str(r[base + 1]) if r[base + 1] is not None else None,
        root_org_id=str(r[base + 2]),
        path=r[base + 3],
        depth=r[base + 4],
        level=r[base + 5],
        name=r[base + 6],
        kind=r[base + 7],
        status=r[base + 8],
        created_at=r[base + 9],
    )


class PostgresMembersDao(MembersDao):
    def __init__(self, database) -> None:
        self._db = database

    def add_membership(self, user_id: str, org_id: str) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO org.memberships (user_id, org_id) VALUES (%s, %s) "
                "ON CONFLICT (user_id, org_id) DO NOTHING",
                (user_id, org_id))

    def add_role(self, user_id: str, org_id: str, role: str, inherits_down: bool) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO org.role_assignments (user_id, org_id, role, inherits_down) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (user_id, org_id, role) DO UPDATE SET inherits_down = EXCLUDED.inherits_down",
                (user_id, org_id, role, inherits_down))

    def list_members(
        self, org_id: str
    ) -> list[tuple[UserRecord, list[RoleAssignmentRecord]]]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_USER_COLS}, ra.role, ra.inherits_down "
                "FROM org.memberships m "
                "JOIN org.users u ON u.user_id = m.user_id "
                "LEFT JOIN org.role_assignments ra "
                "  ON ra.user_id = m.user_id AND ra.org_id = m.org_id "
                "WHERE m.org_id = %s "
                "ORDER BY u.subject, ra.role", (org_id,))
            return _group_by_user(cur.fetchall())

    def list_orgs_for_user(
        self, subject: str
    ) -> list[tuple[OrganizationRecord, list[RoleAssignmentRecord]]]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_ORG_COLS}, ra.role, ra.inherits_down "
                "FROM org.memberships m "
                "JOIN org.users u ON u.user_id = m.user_id "
                "JOIN org.organizations o ON o.org_id = m.org_id "
                "LEFT JOIN org.role_assignments ra "
                "  ON ra.user_id = m.user_id AND ra.org_id = m.org_id "
                "WHERE u.subject = %s "
                "ORDER BY o.path, ra.role", (subject,))
            return _group_by_org(cur.fetchall())


def _group_by_user(rows) -> list[tuple[UserRecord, list[RoleAssignmentRecord]]]:
    out: list[tuple[UserRecord, list[RoleAssignmentRecord]]] = []
    index: dict[str, int] = {}
    for r in rows:
        user = _user(r)
        role, inherits = r[5], r[6]
        if user.user_id not in index:
            index[user.user_id] = len(out)
            out.append((user, []))
        if role is not None:
            out[index[user.user_id]][1].append(
                RoleAssignmentRecord(role=role, inherits_down=inherits))
    return out


def _group_by_org(rows) -> list[tuple[OrganizationRecord, list[RoleAssignmentRecord]]]:
    out: list[tuple[OrganizationRecord, list[RoleAssignmentRecord]]] = []
    index: dict[str, int] = {}
    for r in rows:
        org = _org(r)
        role, inherits = r[10], r[11]
        if org.org_id not in index:
            index[org.org_id] = len(out)
            out.append((org, []))
        if role is not None:
            out[index[org.org_id]][1].append(
                RoleAssignmentRecord(role=role, inherits_down=inherits))
    return out
