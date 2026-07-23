"""PostgreSQL-backed persistence of global user identities."""
from __future__ import annotations

from org_management_api.common.utilities import new_id, utc_now
from org_management_api.dtos.common import UserRecord
from org_management_api.interfaces.daos import UsersDao

_COLUMNS = "user_id, subject, email, display_name, created_at"


def _row(r: tuple) -> UserRecord:
    return UserRecord(
        user_id=str(r[0]), subject=r[1], email=r[2], display_name=r[3], created_at=r[4])


class PostgresUsersDao(UsersDao):
    def __init__(self, database) -> None:
        self._db = database

    def get_by_subject(self, subject: str) -> UserRecord | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.users WHERE subject = %s", (subject,))
            row = cur.fetchone()
            return _row(row) if row else None

    def get_or_create(
        self, subject: str, email: str | None, display_name: str | None
    ) -> UserRecord:
        with self._db.connection() as conn:
            cur = conn.cursor()
            # Idempotent create-if-missing keyed on the unique subject.
            cur.execute(
                f"INSERT INTO org.users ({_COLUMNS}) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (subject) DO NOTHING "
                f"RETURNING {_COLUMNS}",
                (new_id(), subject, email, display_name, utc_now()))
            row = cur.fetchone()
            if row:
                return _row(row)
            cur.execute(
                f"SELECT {_COLUMNS} FROM org.users WHERE subject = %s", (subject,))
            return _row(cur.fetchone())
