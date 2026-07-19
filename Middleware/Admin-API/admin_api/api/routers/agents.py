"""Agent configuration endpoints (HTTP concerns + validation only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from admin_api.api.dependencies import provide_manage_agents_facade
from admin_api.dtos.requests import UpsertAgentConfigRequest
from admin_api.dtos.responses import AgentConfigListResponse, AgentConfigResponse
from admin_api.facades.manage_agents import ManageAgentsFacade

router = APIRouter(prefix="/api/v1/admin/agents", tags=["agents"])


@router.get("", response_model=AgentConfigListResponse, operation_id="listAgentConfigs")
def list_agents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    facade: ManageAgentsFacade = Depends(provide_manage_agents_facade),
) -> AgentConfigListResponse:
    return facade.list(limit, offset)


@router.get("/{agent_key}", response_model=AgentConfigResponse, operation_id="getAgentConfig")
def get_agent(
    agent_key: str,
    facade: ManageAgentsFacade = Depends(provide_manage_agents_facade),
) -> AgentConfigResponse:
    return facade.get(agent_key)


@router.put("/{agent_key}", response_model=AgentConfigResponse, operation_id="upsertAgentConfig")
def upsert_agent(
    agent_key: str,
    request: UpsertAgentConfigRequest,
    facade: ManageAgentsFacade = Depends(provide_manage_agents_facade),
) -> AgentConfigResponse:
    return facade.upsert(agent_key, request)
