"""Translate domain exceptions into standard HTTP error responses."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from org_management_api.common.exceptions import OrgManagementError


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(OrgManagementError)
    async def _handle_domain_error(_: Request, exc: OrgManagementError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, str(exc)),
        )
