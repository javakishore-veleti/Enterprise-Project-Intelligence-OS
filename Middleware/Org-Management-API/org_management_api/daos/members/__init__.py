"""PostgreSQL-backed persistence of memberships + role assignments.

A user is a *member* of an org (memberships) and separately holds zero-or-more
*roles* there (role_assignments). List queries LEFT JOIN roles onto memberships
and group per member/org in Python.
"""
from __future__ import annotations

from org_management_api.common.utilities import escape_like
from org_management_api.dtos.common import (
    InheritedRoleRecord,
    MemberPage,
    MemberRecord,
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

    def list_members_page(
        self,
        org_id: str,
        q: str | None,
        role: str | None,
        limit: int,
        offset: int,
        ancestor_org_ids: list[str],
    ) -> MemberPage:
        where = "m.org_id = %s"
        params: list = [org_id]
        if q:
            like = f"%{escape_like(q)}%"
            where += (" AND (u.subject ILIKE %s ESCAPE '\\' "
                      "OR u.display_name ILIKE %s ESCAPE '\\' "
                      "OR u.email ILIKE %s ESCAPE '\\')")
            params += [like, like, like]
        if role:
            where += (" AND EXISTS (SELECT 1 FROM org.role_assignments ra "
                      "WHERE ra.user_id = m.user_id AND ra.org_id = m.org_id AND ra.role = %s)")
            params.append(role)
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM org.memberships m "
                "JOIN org.users u ON u.user_id = m.user_id "
                f"WHERE {where}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {_USER_COLS} FROM org.memberships m "
                "JOIN org.users u ON u.user_id = m.user_id "
                f"WHERE {where} ORDER BY u.subject, u.user_id LIMIT %s OFFSET %s",
                tuple(params) + (limit, offset))
            users = [_user(r) for r in cur.fetchall()]
            if not users:
                return MemberPage(members=[], total=total, offset=offset, limit=limit)

            user_ids = [u.user_id for u in users]
            uph = ",".join(["%s"] * len(user_ids))

            # Direct roles held in THIS org, for the page's users (one query).
            cur.execute(
                "SELECT user_id, role, inherits_down FROM org.role_assignments "
                f"WHERE org_id = %s AND user_id IN ({uph}) ORDER BY role",
                (org_id, *user_ids))
            direct: dict[str, list[RoleAssignmentRecord]] = {}
            for uid, r_role, inh in cur.fetchall():
                direct.setdefault(str(uid), []).append(
                    RoleAssignmentRecord(role=r_role, inherits_down=inh))

            # Inherited roles: assignments the page's users hold in ANCESTOR orgs
            # with inherits_down = true (one query; skipped when there are none).
            inherited: dict[str, list[InheritedRoleRecord]] = {}
            if ancestor_org_ids:
                aph = ",".join(["%s"] * len(ancestor_org_ids))
                cur.execute(
                    "SELECT ra.user_id, ra.role, ra.org_id, o.name, o.level "
                    "FROM org.role_assignments ra "
                    "JOIN org.organizations o ON o.org_id = ra.org_id "
                    "WHERE ra.inherits_down = true "
                    f"AND ra.org_id IN ({aph}) AND ra.user_id IN ({uph}) "
                    "ORDER BY o.level, ra.role",
                    (*ancestor_org_ids, *user_ids))
                for uid, r_role, src_id, src_name, src_level in cur.fetchall():
                    inherited.setdefault(str(uid), []).append(
                        InheritedRoleRecord(
                            role=r_role, source_org_id=str(src_id),
                            source_org_name=src_name, source_org_level=src_level))

            members = [
                MemberRecord(
                    user=u,
                    direct_roles=direct.get(u.user_id, []),
                    inherited_roles=inherited.get(u.user_id, []),
                )
                for u in users
            ]
            return MemberPage(members=members, total=total, offset=offset, limit=limit)

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
