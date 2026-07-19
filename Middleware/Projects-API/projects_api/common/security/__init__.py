"""Security primitives (placeholder for the foundation slice)."""
from __future__ import annotations

from projects_api.common.models import TypedModel


class Principal(TypedModel):
    """The authenticated caller. Anonymous until auth is wired in."""

    subject: str = "anonymous"
    roles: tuple[str, ...] = ()
