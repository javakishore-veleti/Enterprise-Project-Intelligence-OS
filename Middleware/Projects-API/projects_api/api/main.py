"""FastAPI application factory for the Projects API."""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from projects_api.api.exception_handlers import register_exception_handlers

_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:4200,http://localhost:4201,http://127.0.0.1:4200,http://127.0.0.1:4201",
).split(",")
from projects_api.api.routers import health, project_groups, projects
from projects_api.common.configuration import get_settings
from projects_api.common.logging import configure_logging
from projects_api.common.security import authenticate


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

    app.add_middleware(
        CORSMiddleware, allow_origins=_CORS_ORIGINS, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(projects.router, dependencies=[Depends(authenticate)])  # opt-in auth
    app.include_router(project_groups.router, dependencies=[Depends(authenticate)])  # opt-in auth
    return app


app = create_app()
