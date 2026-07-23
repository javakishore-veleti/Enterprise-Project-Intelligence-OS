"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the Projects API (reads the MongoDB evidence store)."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    service_name: str = "projects-api"
    service_port: int = Field(default=8003, alias="PROJECTS_API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    api_key: str = Field(default="", alias="API_KEY")

    mongo_uri: str = Field(default="mongodb://localhost:27017/epi_os", alias="MONGO_URI")
    mongo_database: str = Field(default="epi_os", alias="MONGO_DATABASE")

    # Org-Management-API (Phase-2 multi-tenancy): resolves the project-key set a
    # user/org may see. Absent org headers => this is never called (behavior
    # unchanged); when it is unreachable the read path degrades to no org scope.
    org_api_base_url: str = Field(
        default="http://localhost:8005", alias="ORG_API_BASE_URL"
    )

    default_page_size: int = Field(default=25, ge=1, le=200)
    max_page_size: int = Field(default=200, ge=1, le=1000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
