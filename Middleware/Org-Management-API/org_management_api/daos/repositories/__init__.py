"""PostgreSQL-backed persistence of repositories, tracker projects, and grants."""
from __future__ import annotations

import json

from org_management_api.common.utilities import escape_like, new_id
from org_management_api.dtos.common import (
    GrantPage,
    RepositoryGrantRecord,
    RepositoryPage,
    RepositoryRecord,
    TrackerProjectPage,
    TrackerProjectRecord,
)
from org_management_api.interfaces.daos import RepositoriesDao

_REPO_COLS = (
    "repo_id, org_id, root_org_id, provider, external_account, "
    "connection_config, visibility_scope, created_at"
)
_TP_COLS = "tracker_project_id, repo_id, external_key, name"


def _obj(v):
    if isinstance(v, str):
        v = json.loads(v)
    return dict(v or {})


def _repo(r: tuple) -> RepositoryRecord:
    return RepositoryRecord(
        repo_id=str(r[0]), org_id=str(r[1]), root_org_id=str(r[2]), provider=r[3],
        external_account=r[4], connection_config=_obj(r[5]), visibility_scope=r[6],
        created_at=r[7])


def _tp(r: tuple) -> TrackerProjectRecord:
    return TrackerProjectRecord(
        tracker_project_id=str(r[0]), repo_id=str(r[1]), external_key=r[2], name=r[3])


class PostgresRepositoriesDao(RepositoriesDao):
    def __init__(self, database) -> None:
        self._db = database

    def insert_repo(self, record: RepositoryRecord) -> RepositoryRecord:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO org.repositories ({_REPO_COLS}) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s) "
                f"RETURNING {_REPO_COLS}",
                (record.repo_id, record.org_id, record.root_org_id, record.provider,
                 record.external_account, json.dumps(record.connection_config),
                 record.visibility_scope, record.created_at))
            return _repo(cur.fetchone())

    def get_repo(self, repo_id: str) -> RepositoryRecord | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_REPO_COLS} FROM org.repositories WHERE repo_id = %s", (repo_id,))
            row = cur.fetchone()
            return _repo(row) if row else None

    def list_by_org(self, org_id: str) -> list[RepositoryRecord]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_REPO_COLS} FROM org.repositories "
                "WHERE org_id = %s ORDER BY created_at, repo_id", (org_id,))
            return [_repo(r) for r in cur.fetchall()]

    def list_by_org_page(
        self, org_id: str, q: str | None, limit: int, offset: int
    ) -> RepositoryPage:
        where = "org_id = %s"
        params: list = [org_id]
        if q:
            like = f"%{escape_like(q)}%"
            where += " AND (provider ILIKE %s ESCAPE '\\' OR external_account ILIKE %s ESCAPE '\\')"
            params += [like, like]
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM org.repositories WHERE {where}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {_REPO_COLS} FROM org.repositories WHERE {where} "
                "ORDER BY created_at, repo_id LIMIT %s OFFSET %s",
                tuple(params) + (limit, offset))
            rows = [_repo(r) for r in cur.fetchall()]
            return RepositoryPage(repositories=rows, total=total, offset=offset, limit=limit)

    def update_visibility(self, repo_id: str, visibility_scope: str) -> RepositoryRecord | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE org.repositories SET visibility_scope = %s "
                f"WHERE repo_id = %s RETURNING {_REPO_COLS}",
                (visibility_scope, repo_id))
            row = cur.fetchone()
            return _repo(row) if row else None

    def insert_tracker_projects(
        self, repo_id: str, projects: list[tuple[str, str | None]]
    ) -> list[TrackerProjectRecord]:
        out: list[TrackerProjectRecord] = []
        with self._db.connection() as conn:
            cur = conn.cursor()
            for external_key, name in projects:
                cur.execute(
                    f"INSERT INTO org.tracker_projects ({_TP_COLS}) VALUES (%s,%s,%s,%s) "
                    "ON CONFLICT (repo_id, external_key) DO UPDATE SET name = EXCLUDED.name "
                    f"RETURNING {_TP_COLS}",
                    (new_id(), repo_id, external_key, name))
                out.append(_tp(cur.fetchone()))
        return out

    def list_tracker_projects(self, repo_id: str) -> list[TrackerProjectRecord]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_TP_COLS} FROM org.tracker_projects "
                "WHERE repo_id = %s ORDER BY external_key", (repo_id,))
            return [_tp(r) for r in cur.fetchall()]

    def list_tracker_projects_page(
        self, repo_id: str, q: str | None, limit: int, offset: int
    ) -> TrackerProjectPage:
        where = "repo_id = %s"
        params: list = [repo_id]
        if q:
            like = f"%{escape_like(q)}%"
            where += " AND (external_key ILIKE %s ESCAPE '\\' OR name ILIKE %s ESCAPE '\\')"
            params += [like, like]
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM org.tracker_projects WHERE {where}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {_TP_COLS} FROM org.tracker_projects WHERE {where} "
                "ORDER BY external_key LIMIT %s OFFSET %s",
                tuple(params) + (limit, offset))
            rows = [_tp(r) for r in cur.fetchall()]
            return TrackerProjectPage(projects=rows, total=total, offset=offset, limit=limit)

    def add_grant(
        self, repo_id: str, grantee_org_id: str, direction: str
    ) -> RepositoryGrantRecord:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO org.repository_grants (repo_id, grantee_org_id, direction) "
                "VALUES (%s,%s,%s) "
                "ON CONFLICT (repo_id, grantee_org_id) DO UPDATE SET direction = EXCLUDED.direction "
                "RETURNING repo_id, grantee_org_id, direction",
                (repo_id, grantee_org_id, direction))
            r = cur.fetchone()
            return RepositoryGrantRecord(
                repo_id=str(r[0]), grantee_org_id=str(r[1]), direction=r[2])

    def list_grants_page(self, repo_id: str, limit: int, offset: int) -> GrantPage:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM org.repository_grants WHERE repo_id = %s", (repo_id,))
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT repo_id, grantee_org_id, direction FROM org.repository_grants "
                "WHERE repo_id = %s ORDER BY grantee_org_id LIMIT %s OFFSET %s",
                (repo_id, limit, offset))
            rows = [
                RepositoryGrantRecord(
                    repo_id=str(r[0]), grantee_org_id=str(r[1]), direction=r[2])
                for r in cur.fetchall()
            ]
            return GrantPage(grants=rows, total=total, offset=offset, limit=limit)
