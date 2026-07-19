"""Translate domain exceptions into standard HTTP error responses."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from projects_api.common.exceptions import ProjectsError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProjectsError)
    async def _handle_domain_error(_: Request, exc: ProjectsError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )
