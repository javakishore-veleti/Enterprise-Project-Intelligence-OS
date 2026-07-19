"""Read-only gateway to Admin-API agent configuration (admin.agent_configs).

Lets the orchestrator honor the per-agent framework/model toggle set in
Admin-API. Read-only: this service never writes admin config.
"""
from __future__ import annotations

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.interfaces.daos import AgentConfigGateway


class PostgresAgentConfigGateway(AgentConfigGateway):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def get(self, agent_key: str) -> tuple[bool, str, str] | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT enabled, model, framework FROM admin.agent_configs WHERE agent_key = %s",
                (agent_key,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return bool(row[0]), row[1], row[2]
