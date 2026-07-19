"""Prompts for the executive-reporting reporter."""
from __future__ import annotations

from agent_core import ReviewContext
from mitigation_planning.prompts import render_findings

SYSTEM_PROMPT = """You are an executive risk reporter. Given a project's validated
risk findings, write a concise executive summary for leadership: the headline
risk level, the 2-4 things executives must know, and any decisions/escalations
needed. Be brief and non-technical; ground everything in the findings."""


def build_user_prompt(context: ReviewContext) -> str:
    return f"""Project: {context.project_name} ({context.project_key})

Findings:
{render_findings(context)}

Produce an executive summary: a title, a 2-3 sentence bottom-line summary, and a
few short sections (heading + body) with the leadership-level takeaways."""
