"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the Ingestion API.

    Values come from environment variables (see repository ``.env.example``).
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    service_name: str = "ingestion-api"
    service_port: int = Field(default=8001, alias="INGESTION_API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    pg_host: str = Field(default="localhost", alias="PG_HOST")
    pg_port: int = Field(default=5432, alias="PG_PORT")
    pg_user: str = Field(default="epi_os", alias="PG_USER")
    pg_password: str = Field(default="epi_os", alias="PG_PASSWORD")
    pg_database: str = Field(default="epi_os", alias="PG_DATABASE")

    # Gateway to Airflow (operational workflow trigger). Stubbed in the
    # foundation slice; real deployments point this at the Airflow REST API.
    airflow_base_url: str = Field(default="http://localhost:8080", alias="AIRFLOW_BASE_URL")


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
