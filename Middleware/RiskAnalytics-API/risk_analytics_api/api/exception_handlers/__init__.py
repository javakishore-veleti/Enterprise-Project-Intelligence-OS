"""Translate domain exceptions into standard HTTP error responses."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from risk_analytics_api.common.exceptions import RiskAnalyticsError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RiskAnalyticsError)
    async def _handle_domain_error(_: Request, exc: RiskAnalyticsError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )
