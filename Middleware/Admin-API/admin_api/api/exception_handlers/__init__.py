"""Translate domain exceptions into standard HTTP error responses."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from admin_api.common.exceptions import AdminError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AdminError)
    async def _handle_domain_error(_: Request, exc: AdminError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )
