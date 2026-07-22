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
    """

    project_key: str = Field(min_length=1)
    requested_by: str | None = Field(default=None)


class ScenarioRequest(TypedModel):
    """Run a digital-twin what-if for one project.

    ``scenario`` is a free-text what-if (e.g. "move 2 engineers to Payments").
    Deterministic code re-forecasts under the scenario and propagates the impact
    along dependency links + shared contributors; the LLM narrates the trade-off.
    """

    project_key: str = Field(min_length=1)
    scenario: str = Field(min_length=1, description="Free-text what-if to simulate.")
    requested_by: str | None = Field(default=None)


class DecisionRequest(TypedModel):
    """Ask the Decide engine for prescriptive decision support on one project.

    Decide leads with OPTIONS. Deterministic code assembles the evidence (the
    delivery forecast, open blockers, top contributors); the LLM (mitigation-
    planning persona) proposes 2-3 decision options — each with prioritized
    actions + suggested owners — plus a comparison narrative.
    """

    project_key: str = Field(min_length=1)
    requested_by: str | None = Field(default=None)
    context: str | None = Field(
        default=None,
        description="Optional free-text steer, e.g. 'we must ship by Q3'.",
    )


class SelectOptionRequest(TypedModel):
    """Choose one of a decision's generated options (its actions become the plan)."""

    option_id: str = Field(min_length=1)
