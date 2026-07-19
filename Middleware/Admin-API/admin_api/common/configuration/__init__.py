"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the Admin API (platform/agent configuration on Postgres)."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    service_name: str = "admin-api"
    service_port: int = Field(default=8002, alias="ADMIN_API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    pg_host: str = Field(default="localhost", alias="PG_HOST")
    pg_port: int = Field(default=5432, alias="PG_PORT")
    pg_user: str = Field(default="epi_os", alias="PG_USER")
    pg_password: str = Field(default="epi_os", alias="PG_PASSWORD")
    pg_database: str = Field(default="epi_os", alias="PG_DATABASE")

    # Default reasoning model + orchestration framework applied to new agents.
    default_agent_model: str = Field(default="claude-opus-4-8", alias="AGENT_MODEL")
    default_agent_framework: str = Field(default="langgraph", alias="AGENT_FRAMEWORK")

    # Governed boundary to the Ingestion API (dataset acquisition is owned there).
    ingestion_api_base_url: str = Field(default="http://localhost:8001", alias="INGESTION_API_BASE_URL")
    default_dataset_id: str = Field(default="public-jira", alias="DEFAULT_DATASET_ID")


@lru_cache
def get_settings() -> Settings:
    return Settings()
