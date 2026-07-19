"""PostgreSQL-backed implementation of the agent-config DAO."""
from __future__ import annotations

from admin_api.daos.connection import Database
from admin_api.dtos.common import AgentFramework
from admin_api.dtos.responses import AgentConfigResponse
from admin_api.interfaces.daos import AgentConfigDao

_COLUMNS = "agent_key, display_name, enabled, model, framework, prompt_ref, updated_by, updated_at"


def _row(r: tuple) -> AgentConfigResponse:
    return AgentConfigResponse(
        agent_key=r[0],
        display_name=r[1],
        enabled=r[2],
        model=r[3],
        framework=AgentFramework(r[4]),
        prompt_ref=r[5],
        updated_by=r[6],
        updated_at=r[7],
    )


class PostgresAgentConfigDao(AgentConfigDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def list(self, limit, offset):
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM admin.agent_configs")
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {_COLUMNS} FROM admin.agent_configs "
                "ORDER BY agent_key LIMIT %s OFFSET %s",
                (limit, offset),
            )
            return [_row(r) for r in cur.fetchall()], total

    def get(self, agent_key):
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM admin.agent_configs WHERE agent_key = %s",
                (agent_key,),
            )
            row = cur.fetchone()
            return _row(row) if row else None

    def upsert(self, config: AgentConfigResponse) -> AgentConfigResponse:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO admin.agent_configs "
                f"({_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (agent_key) DO UPDATE SET "
                "  display_name = EXCLUDED.display_name,"
                "  enabled = EXCLUDED.enabled,"
                "  model = EXCLUDED.model,"
                "  framework = EXCLUDED.framework,"
                "  prompt_ref = EXCLUDED.prompt_ref,"
                "  updated_by = EXCLUDED.updated_by,"
                "  updated_at = EXCLUDED.updated_at "
                f"RETURNING {_COLUMNS}",
                (
                    config.agent_key,
                    config.display_name,
                    config.enabled,
                    config.model,
                    config.framework.value,
                    config.prompt_ref,
                    config.updated_by,
                    config.updated_at,
                ),
            )
            return _row(cur.fetchone())

    def counts(self):
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT count(*), count(*) FILTER (WHERE enabled) FROM admin.agent_configs"
            )
            total, enabled = cur.fetchone()
            return total, enabled
