"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the Org-Management API.

    Values come from environment variables (see repository ``.env.example``).
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    service_name: str = "org-management-api"
    service_port: int = Field(default=8005, alias="ORG_MANAGEMENT_API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API-key auth (opt-in). When enabled, business endpoints require X-API-Key.
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    api_key: str = Field(default="", alias="API_KEY")

    pg_host: str = Field(default="localhost", alias="PG_HOST")
    pg_port: int = Field(default=5432, alias="PG_PORT")
    pg_user: str = Field(default="epi_os", alias="PG_USER")
    pg_password: str = Field(default="epi_os", alias="PG_PASSWORD")
    pg_database: str = Field(default="epi_os", alias="PG_DATABASE")


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
