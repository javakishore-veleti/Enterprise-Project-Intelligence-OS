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

    # API-key auth (opt-in). When enabled, business endpoints require X-API-Key.
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    api_key: str = Field(default="", alias="API_KEY")

    pg_host: str = Field(default="localhost", alias="PG_HOST")
    pg_port: int = Field(default=5432, alias="PG_PORT")
    pg_user: str = Field(default="epi_os", alias="PG_USER")
    pg_password: str = Field(default="epi_os", alias="PG_PASSWORD")
    pg_database: str = Field(default="epi_os", alias="PG_DATABASE")

    # Evidence store (read-only) — used to compute validate/index/reconcile counts.
    mongo_uri: str = Field(default="mongodb://localhost:27017/epi_os", alias="MONGO_URI")
    mongo_database: str = Field(default="epi_os", alias="MONGO_DATABASE")

    # Gateway to Airflow (operational workflow trigger). The dataset-acquire
    # trigger POSTs to the Airflow REST API using these credentials.
    airflow_base_url: str = Field(default="http://localhost:8080", alias="AIRFLOW_BASE_URL")
    airflow_user: str = Field(default="admin", alias="AIRFLOW_ADMIN_USER")
    airflow_password: str = Field(default="admin", alias="AIRFLOW_ADMIN_PASSWORD")

    # The dataset the "Initial Dataset" download manages.
    default_dataset_id: str = Field(default="public-jira", alias="DEFAULT_DATASET_ID")
    acquire_dag_id: str = Field(default="project_dataset_acquire", alias="ACQUIRE_DAG_ID")
    ingest_dag_id: str = Field(default="project_dataset_ingest", alias="INGEST_DAG_ID")
    metrics_dag_id: str = Field(default="project_metrics_compute", alias="METRICS_DAG_ID")
    sync_dag_id: str = Field(default="tracker_repository_sync", alias="TRACKER_SYNC_DAG_ID")
    # Auto-trigger metric computation when an ingestion run completes.
    auto_compute_metrics: bool = Field(default=True, alias="AUTO_COMPUTE_METRICS")


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
