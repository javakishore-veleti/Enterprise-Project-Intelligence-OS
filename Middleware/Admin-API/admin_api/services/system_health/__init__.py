"""System health service — aggregate platform health as seen by Admin API."""
from __future__ import annotations

from admin_api.common.configuration import Settings
from admin_api.daos.connection import Database
from admin_api.dtos.responses import SystemHealthResponse
from admin_api.interfaces.daos import AgentConfigDao
from admin_api.interfaces.services import SystemHealthService


class DefaultSystemHealthService(SystemHealthService):
    def __init__(self, database: Database, config_dao: AgentConfigDao, settings: Settings) -> None:
        self._db = database
        self._config = config_dao
        self._settings = settings

    def snapshot(self) -> SystemHealthResponse:
        try:
            self._db.ping()
            pg_status = "ok"
            total, enabled = self._config.counts()
        except Exception:
            return SystemHealthResponse(
                status="degraded",
                service=self._settings.service_name,
                dependencies={"postgresql": "unavailable"},
                agent_count=0,
                enabled_agent_count=0,
            )
        return SystemHealthResponse(
            status="ok",
            service=self._settings.service_name,
            dependencies={"postgresql": pg_status},
            agent_count=total,
            enabled_agent_count=enabled,
        )
