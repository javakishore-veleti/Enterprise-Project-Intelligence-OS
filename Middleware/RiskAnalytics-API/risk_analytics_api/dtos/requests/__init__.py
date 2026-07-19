"""Inbound request DTOs (validated at the API boundary)."""
from __future__ import annotations

from pydantic import Field

from risk_analytics_api.common.models import TypedModel


class StartAnalysisRequest(TypedModel):
    """Start a risk analysis for a project."""

    agents: list[str] = Field(
        default_factory=lambda: ["schedule_risk"],
        description="Detector agent keys to run. Only implemented agents execute.",
    )
    include_review: bool = Field(
        default=False,
        description="Run the review pipeline (validate/dedup/correlate/score/critic + reports) after detection.",
    )
    requested_by: str = Field(default="system", min_length=1)
