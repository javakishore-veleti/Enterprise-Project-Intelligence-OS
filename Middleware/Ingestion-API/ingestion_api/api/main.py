"""FastAPI application factory for the Ingestion API."""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ingestion_api.api.exception_handlers import register_exception_handlers

_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:4200,http://localhost:4201,http://127.0.0.1:4200,http://127.0.0.1:4201",
).split(",")
from ingestion_api.api.routers import (
    dataset_ingestion,
    datasets,
    health,
    ingestion,
    operations,
    tracker_sync,
)
from ingestion_api.common.configuration import get_settings
from ingestion_api.common.logging import configure_logging
from ingestion_api.common.security import authenticate


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

    app.add_middleware(
        CORSMiddleware, allow_origins=_CORS_ORIGINS, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)  # public
    secured = [Depends(authenticate)]  # opt-in API-key auth (no-op unless AUTH_ENABLED)
    app.include_router(ingestion.router, dependencies=secured)
    app.include_router(operations.router, dependencies=secured)
    app.include_router(datasets.router, dependencies=secured)
    app.include_router(dataset_ingestion.router, dependencies=secured)
    app.include_router(tracker_sync.router, dependencies=secured)
    return app


app = create_app()
