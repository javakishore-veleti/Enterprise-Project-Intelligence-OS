"""FastAPI application factory for the Org-Management API."""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from org_management_api.api.exception_handlers import register_exception_handlers

_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:4200,http://localhost:4201,http://127.0.0.1:4200,http://127.0.0.1:4201",
).split(",")
from org_management_api.api.routers import (
    access,
    health,
    members,
    organizations,
    repositories,
)
from org_management_api.common.configuration import get_settings
from org_management_api.common.logging import configure_logging
from org_management_api.common.security import authenticate


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Org-Management API",
        version="0.1.0",
        description="Organization + multi-tenancy management for Enterprise Project Intelligence OS.",
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
    app.include_router(organizations.router, dependencies=secured)
    app.include_router(members.router, dependencies=secured)
    app.include_router(repositories.router, dependencies=secured)
    app.include_router(access.router, dependencies=secured)
    return app


app = create_app()
