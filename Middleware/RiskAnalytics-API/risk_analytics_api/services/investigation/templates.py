"""Pre-configured investigation templates.

A template is a light-touch bias on the Investigation Agent's focus: its ``steps``
name the investigative angles / tool-emphasis, which get appended to the agent's
system prompt as an "Emphasize: ..." directive (NOT a hard tool restriction — the
agent still ranges freely over the evidence tools). These defaults live in code
for now; a later migration can make them user-editable (hence ``editable``).
"""
from __future__ import annotations

from risk_analytics_api.dtos.responses import InvestigationTemplateResponse

#: Applied when no (or an unknown) template_key is supplied.
DEFAULT_TEMPLATE_KEY = "full"

_TEMPLATES: tuple[InvestigationTemplateResponse, ...] = (
    InvestigationTemplateResponse(
        template_key="full",
        name="Full investigation",
        description="Investigate all delivery-risk angles for the project.",
        steps=[
            "quality & reopen churn",
            "dependency stalls",
            "resourcing / bus-factor",
            "issue aging",
            "backlog growth",
        ],
        editable=True,
    ),
    InvestigationTemplateResponse(
        template_key="quality",
        name="Quality & reopen churn",
        description="Focus on reopen churn and defect quality signals.",
        steps=[
            "reopen rate and reopened issues",
            "critical-defect ratio",
            "status-change churn",
        ],
        editable=True,
    ),
    InvestigationTemplateResponse(
        template_key="delivery",
        name="Delivery blockers & dependencies",
        description="Focus on blockers, dependency stalls, and aging work.",
        steps=[
            "open blockers",
            "dependency links and stalls",
            "aging backlog",
        ],
        editable=True,
    ),
)

_BY_KEY: dict[str, InvestigationTemplateResponse] = {t.template_key: t for t in _TEMPLATES}


def list_templates() -> list[InvestigationTemplateResponse]:
    """All templates in display order."""
    return list(_TEMPLATES)


def resolve_template(template_key: str | None) -> InvestigationTemplateResponse:
    """Return the requested template, falling back to the default when absent/unknown."""
    return _BY_KEY.get(template_key or DEFAULT_TEMPLATE_KEY, _BY_KEY[DEFAULT_TEMPLATE_KEY])


def emphasis_for(template: InvestigationTemplateResponse) -> str:
    """The prompt-bias directive text derived from a template's steps."""
    return "; ".join(template.steps)
