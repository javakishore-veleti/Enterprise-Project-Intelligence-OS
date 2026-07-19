"""FastAPI application factory for the Projects API."""
from __future__ import annotations

from fastapi import FastAPI

from projects_api.api.exception_handlers import register_exception_handlers
from projects_api.api.routers import health, projects
from projects_api.common.configuration import get_settings
from projects_api.common.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Projects API",
        version="0.1.0",
        description="Project intelligence queries over the evidence store for Enterprise Project Intelligence OS.",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(projects.router)
    return app


app = create_app()
