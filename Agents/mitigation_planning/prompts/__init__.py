"""Prompts for the mitigation-planning reporter."""
from __future__ import annotations

from agent_core import ReviewContext


def render_findings(context: ReviewContext) -> str:
    return "\n".join(
        f"[{i}] {f.severity.value.upper()} {f.risk_category.value} (score {f.score}): "
        f"{f.explanation}"
        + (f"  actions: {'; '.join(f.recommended_actions)}" if f.recommended_actions else "")
        for i, f in enumerate(context.findings)
    )


SYSTEM_PROMPT = """You are a delivery risk mitigation planner. Given a project's
validated risk findings, produce a prioritized, actionable mitigation plan.
Group actions by theme, sequence them (what to do first), and keep it concrete
and grounded in the findings. Do not invent risks that are not in the findings."""


def build_user_prompt(context: ReviewContext) -> str:
    return f"""Project: {context.project_name} ({context.project_key})

Findings:
{render_findings(context)}

Produce a mitigation plan: a title, a 2-3 sentence summary, and sections (each
with a heading and body) covering the prioritized mitigation actions."""
