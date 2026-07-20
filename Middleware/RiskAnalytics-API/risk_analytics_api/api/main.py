"""FastAPI application factory for the Risk Analytics API."""
from __future__ import annotations

from fastapi import FastAPI

from fastapi import Depends

from risk_analytics_api.api.exception_handlers import register_exception_handlers
from risk_analytics_api.api.routers import analysis, health
from risk_analytics_api.common.configuration import get_settings
from risk_analytics_api.common.logging import configure_logging
from risk_analytics_api.common.security import authenticate
from risk_analytics_api.common.tracing import configure_tracing


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings)  # LangSmith (no-op unless enabled + key present)

    app = FastAPI(
        title="Risk Analytics API",
        version="0.1.0",
        description="Multi-agent risk analysis (LangGraph) over evidence for Enterprise Project Intelligence OS.",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(analysis.router, dependencies=[Depends(authenticate)])  # opt-in auth
    return app


app = create_app()
