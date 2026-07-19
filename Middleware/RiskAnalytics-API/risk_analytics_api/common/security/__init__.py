"""Security primitives (placeholder for the foundation slice)."""
from __future__ import annotations

from risk_analytics_api.common.models import TypedModel


class Principal(TypedModel):
    subject: str = "anonymous"
    roles: tuple[str, ...] = ()
