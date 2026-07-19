"""Prompts for the project-reporting reporter."""
from __future__ import annotations

from agent_core import ReviewContext
from mitigation_planning.prompts import render_findings

SYSTEM_PROMPT = """You are a project risk reporter. Given a project's validated,
scored risk findings, write a clear project-level risk report for a delivery
lead: the overall risk posture, the most important risks and why, and what to
watch. Ground everything in the findings; do not introduce new risks."""


def build_user_prompt(context: ReviewContext) -> str:
    return f"""Project: {context.project_name} ({context.project_key})

Findings (highest priority first):
{render_findings(context)}

Produce a project risk report: a title, a 2-3 sentence executive summary, and
sections (heading + body) covering the key risks and recommended focus."""
