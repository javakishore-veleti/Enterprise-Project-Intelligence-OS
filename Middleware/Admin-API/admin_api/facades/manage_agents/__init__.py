"""Use case: manage agent runtime configuration."""
from __future__ import annotations

from admin_api.dtos.requests import UpsertAgentConfigRequest
from admin_api.dtos.responses import AgentConfigListResponse, AgentConfigResponse
from admin_api.interfaces.facades import ManageAgentsUseCase
from admin_api.interfaces.services import AgentManagementService


class ManageAgentsFacade(ManageAgentsUseCase):
    def __init__(self, service: AgentManagementService) -> None:
        self._service = service

    def list(self, limit: int, offset: int) -> AgentConfigListResponse:
        return self._service.list(limit, offset)

    def get(self, agent_key: str) -> AgentConfigResponse:
        return self._service.get(agent_key)

    def upsert(self, agent_key: str, request: UpsertAgentConfigRequest) -> AgentConfigResponse:
        return self._service.upsert(agent_key, request)
