"""Security primitives: API-key authentication.

Opt-in (``AUTH_ENABLED``): when off, every request resolves to an anonymous
principal (local dev / tests). When on, requests must carry a matching
``X-API-Key`` header or they are rejected with 401. Health endpoints stay public.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from ingestion_api.common.configuration import get_settings
from ingestion_api.common.models import TypedModel


class Principal(TypedModel):
    """The authenticated caller."""

    subject: str = "anonymous"
    roles: tuple[str, ...] = ()


def verify_api_key(provided: str | None, expected: str, enabled: bool) -> bool:
    if not enabled:
        return True
    return bool(expected) and provided == expected


def authenticate(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> Principal:
    settings = get_settings()
    if not settings.auth_enabled:
        return Principal()
    if not verify_api_key(x_api_key, settings.api_key, settings.auth_enabled):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing X-API-Key")
    return Principal(subject="api-key", roles=("service",))
