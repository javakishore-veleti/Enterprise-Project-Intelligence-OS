"""Outbound response DTOs (never expose raw database entities)."""
from __future__ import annotations

from datetime import datetime

from admin_api.common.models import TypedModel
from admin_api.dtos.common import AgentFramework, PageMeta


class AgentConfigResponse(TypedModel):
    """Public view of an agent's runtime configuration."""

    agent_key: str
    display_name: str
    enabled: bool
    model: str
    framework: AgentFramework
    prompt_ref: str | None
    updated_by: str
    updated_at: datetime


class AgentConfigListResponse(TypedModel):
    items: list[AgentConfigResponse]
    page: PageMeta


class AuditEventResponse(TypedModel):
    """An administrative audit record."""

    event_id: str
    entity_type: str
    entity_key: str
    action: str
    actor: str
    details: dict
    created_at: datetime


class AuditListResponse(TypedModel):
    items: list[AuditEventResponse]
    page: PageMeta


class SystemHealthResponse(TypedModel):
    """Aggregate platform health as seen by the Admin API."""

    status: str
    service: str
    dependencies: dict[str, str]
    agent_count: int
    enabled_agent_count: int


class HealthResponse(TypedModel):
    status: str
    service: str
    dependencies: dict[str, str] = {}
