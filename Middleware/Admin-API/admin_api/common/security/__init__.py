"""Security primitives (placeholder for the foundation slice)."""
from __future__ import annotations

from admin_api.common.models import TypedModel


class Principal(TypedModel):
    """The authenticated caller. Anonymous until auth is wired in.

    Admin operations will later require an authorized principal; audit events
    already record the actor so this wires in cleanly.
    """

    subject: str = "anonymous"
    roles: tuple[str, ...] = ()
