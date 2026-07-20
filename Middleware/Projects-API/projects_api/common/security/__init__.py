"""Security primitives: API-key authentication (opt-in via AUTH_ENABLED)."""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from projects_api.common.configuration import get_settings
from projects_api.common.models import TypedModel


class Principal(TypedModel):
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
