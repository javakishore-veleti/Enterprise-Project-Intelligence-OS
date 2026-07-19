"""FastAPI application factory for the Ingestion API."""
from __future__ import annotations

from fastapi import FastAPI

from ingestion_api.api.exception_handlers import register_exception_handlers
from ingestion_api.api.routers import datasets, health, ingestion, operations
from ingestion_api.common.configuration import get_settings
from ingestion_api.common.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Ingestion API",
        version="0.1.0",
        description="Dataset ingestion management for Enterprise Project Intelligence OS.",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(ingestion.router)
    app.include_router(operations.router)
    app.include_router(datasets.router)
    return app


app = create_app()
