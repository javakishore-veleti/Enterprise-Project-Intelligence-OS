"""Inbound request DTOs (validated at the API boundary)."""
from __future__ import annotations

from pydantic import Field

from admin_api.common.models import TypedModel
from admin_api.dtos.common import AgentFramework


class UpsertAgentConfigRequest(TypedModel):
    """Create or update an agent's runtime configuration."""

    enabled: bool = True
    model: str = Field(..., min_length=1, description="Reasoning model id, e.g. claude-opus-4-8.")
    framework: AgentFramework = AgentFramework.LANGGRAPH
    prompt_ref: str | None = Field(default=None, description="Reference/version of the agent prompt.")
    updated_by: str = Field(default="admin", min_length=1)
