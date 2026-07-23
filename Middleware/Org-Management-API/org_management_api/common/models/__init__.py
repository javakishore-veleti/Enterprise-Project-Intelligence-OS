"""Shared typed base model.

Every cross-layer object (DTOs, service/DAO request+response objects) inherits
from ``TypedModel`` so that untyped dicts are never passed between layers.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TypedModel(BaseModel):
    """Immutable, strictly-validated base for all inter-layer objects."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )
