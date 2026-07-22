"""Inbound request DTOs (validated at the API boundary)."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

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


class StartPortfolioAnalysisRequest(TypedModel):
    """Start a portfolio (multi-project) risk analysis."""

    agents: list[str] = Field(default_factory=lambda: ["schedule_risk"])
    project_keys: list[str] = Field(
        default_factory=list,
        description="Projects to include. Empty -> resolve from the evidence store (bounded).",
    )
    requested_by: str = Field(default="system", min_length=1)


class InvestigateRequest(TypedModel):
    """Point the autonomous Investigation Agent at a project.

    The agent forms hypotheses, calls evidence-store tools to gather bounded
    facts, reasons, and concludes with a root cause + causal chain.
    """

    project_key: str = Field(min_length=1)
    question: str | None = Field(
        default=None,
        description="Optional free-text steer, e.g. 'why is APACHE slipping?'.",
    )
    template_key: str | None = Field(
        default=None,
        description="Investigation template to bias the agent's focus. Unknown/absent -> 'full'.",
    )
    requested_by: str | None = Field(default=None)


class ForecastRequest(TypedModel):
    """Ask the Predict engine for a delivery forecast on one project.

    Deterministic code computes the on-time probability + credible interval +
    slip range + drivers from the project's metric-history trajectory; the LLM
    (delivery-forecasting persona) then narrates it (bull/bear/would-change-mind).

    A forecast can be scoped to a sub-project subject: ``subject_type`` selects
    the granularity (default ``"project"`` = current whole-project behavior), and
    ``subject_value`` names the release / component / tag to filter the evidence
    issue set to. ``subject_value`` is required whenever ``subject_type`` is not
    ``"project"``.
    """

    project_key: str = Field(min_length=1)
    subject_type: Literal["project", "release", "component", "tag"] = Field(
        default="project",
        description="Forecast granularity. 'project' (default) = whole project.",
    )
    subject_value: str | None = Field(
        default=None,
        description="The release/component/tag value to scope to (required when "
        "subject_type != 'project').",
    )
    requested_by: str | None = Field(default=None)

    @model_validator(mode="after")
    def _require_subject_value(self) -> "ForecastRequest":
        if self.subject_type != "project" and not (self.subject_value or "").strip():
            raise ValueError("subject_value is required when subject_type != 'project'")
        return self


class ScenarioRequest(TypedModel):
    """Run a digital-twin what-if for one project.

    ``scenario`` is a free-text what-if (e.g. "move 2 engineers to Payments").
    Deterministic code re-forecasts under the scenario and propagates the impact
    along dependency links + shared contributors; the LLM narrates the trade-off.
    """

    project_key: str = Field(min_length=1)
    scenario: str = Field(min_length=1, description="Free-text what-if to simulate.")
    requested_by: str | None = Field(default=None)
