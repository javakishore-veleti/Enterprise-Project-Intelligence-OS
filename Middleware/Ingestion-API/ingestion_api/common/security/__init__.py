"""Security primitives.

Placeholder for the foundation slice. Real deployments add authentication,
authorization, and request-context propagation here; the API layer resolves an
authenticated principal via a FastAPI dependency that lives in this package.
"""
from __future__ import annotations

from ingestion_api.common.models import TypedModel


class Principal(TypedModel):
    """The authenticated caller. Anonymous until auth is wired in."""

    subject: str = "anonymous"
    roles: tuple[str, ...] = ()
