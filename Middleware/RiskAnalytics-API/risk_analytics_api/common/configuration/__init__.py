"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the Risk Analytics API.

    Reads agent config + persists findings in PostgreSQL; reads the evidence
    store in MongoDB; calls Claude via langchain-anthropic (ANTHROPIC_API_KEY is
    read from the environment by the SDK and is never stored here).
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    service_name: str = "risk-analytics-api"
    service_port: int = Field(default=8004, alias="RISK_ANALYTICS_API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    api_key: str = Field(default="", alias="API_KEY")

    pg_host: str = Field(default="localhost", alias="PG_HOST")
    pg_port: int = Field(default=5432, alias="PG_PORT")
    pg_user: str = Field(default="epi_os", alias="PG_USER")
    pg_password: str = Field(default="epi_os", alias="PG_PASSWORD")
    pg_database: str = Field(default="epi_os", alias="PG_DATABASE")

    mongo_uri: str = Field(default="mongodb://localhost:27017/epi_os", alias="MONGO_URI")
    mongo_database: str = Field(default="epi_os", alias="MONGO_DATABASE")

    # Org-Management-API (Phase-2 multi-tenancy): resolves the project-key set a
    # user/org may see. Absent org headers => this is never called (behavior
    # unchanged); when it is unreachable the read/run path degrades to no org scope.
    org_api_base_url: str = Field(
        default="http://localhost:8005", alias="ORG_API_BASE_URL"
    )

    # Fallback defaults if an agent has no Admin-API config row yet.
    default_agent_model: str = Field(default="claude-opus-4-8", alias="AGENT_MODEL")
    default_agent_framework: str = Field(default="langgraph", alias="AGENT_FRAMEWORK")

    # LangSmith tracing (LangChain/LangGraph auto-trace when enabled + LANGSMITH_API_KEY
    # is in the environment). The key itself is read from the env, never stored here.
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_project: str = Field(
        default="enterprise-project-intelligence-os", alias="LANGSMITH_PROJECT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
