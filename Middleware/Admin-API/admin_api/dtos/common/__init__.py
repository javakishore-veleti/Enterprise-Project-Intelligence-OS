"""Common DTO fragments shared across requests and responses."""
from __future__ import annotations

from enum import StrEnum

from admin_api.common.models import TypedModel


class AgentFramework(StrEnum):
    """Orchestration framework an agent executes under.

    The default is LangGraph; the alternatives are pluggable adapters behind
    each agent's framework-agnostic port (see Agents/README.md). Selecting a
    framework here is how the platform toggles orchestration per agent.
    """

    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    OPENAI_AGENTS = "openai_agents"
    STRANDS = "strands"
    GOOGLE_ADK = "google_adk"
    MS_AGENT_FRAMEWORK = "ms_agent_framework"


class PageMeta(TypedModel):
    total: int
    limit: int
    offset: int
