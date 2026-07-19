"""Agent management service — read/update agent runtime configuration.

Every configuration change is recorded as an audit event (the framework toggle
that the Agents/ adapters read is changed here).
"""
from __future__ import annotations

from admin_api.common.exceptions import NotFoundError
from admin_api.common.utilities import new_id, utc_now
from admin_api.dtos.common import PageMeta
from admin_api.dtos.requests import UpsertAgentConfigRequest
from admin_api.dtos.responses import (
    AgentConfigListResponse,
    AgentConfigResponse,
    AuditEventResponse,
)
from admin_api.interfaces.daos import AgentConfigDao, AuditDao
from admin_api.interfaces.services import AgentManagementService


class DefaultAgentManagementService(AgentManagementService):
    def __init__(self, config_dao: AgentConfigDao, audit_dao: AuditDao) -> None:
        self._config = config_dao
        self._audit = audit_dao

    def list(self, limit: int, offset: int) -> AgentConfigListResponse:
        items, total = self._config.list(limit, offset)
        return AgentConfigListResponse(
            items=items, page=PageMeta(total=total, limit=limit, offset=offset)
        )

    def get(self, agent_key: str) -> AgentConfigResponse:
        config = self._config.get(agent_key)
        if config is None:
            raise NotFoundError(f"agent '{agent_key}' not found")
        return config

    def upsert(self, agent_key: str, request: UpsertAgentConfigRequest) -> AgentConfigResponse:
        existing = self._config.get(agent_key)
        display_name = existing.display_name if existing else agent_key.replace("_", " ").title()
        now = utc_now()
        saved = self._config.upsert(
            AgentConfigResponse(
                agent_key=agent_key,
                display_name=display_name,
                enabled=request.enabled,
                model=request.model,
                framework=request.framework,
                prompt_ref=request.prompt_ref,
                updated_by=request.updated_by,
                updated_at=now,
            )
        )
        self._audit.append(
            AuditEventResponse(
                event_id=new_id(),
                entity_type="agent_config",
                entity_key=agent_key,
                action="created" if existing is None else "updated",
                actor=request.updated_by,
                details={
                    "enabled": saved.enabled,
                    "model": saved.model,
                    "framework": saved.framework.value,
                    "prompt_ref": saved.prompt_ref,
                },
                created_at=now,
            )
        )
        return saved
