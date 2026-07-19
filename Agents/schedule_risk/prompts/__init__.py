"""Prompts for the schedule-risk agent. Shared across all framework adapters."""
from __future__ import annotations

from agent_core import EvidencePackage

SYSTEM_PROMPT = """You are a schedule-risk analyst for software delivery projects.
You are given deterministic, pre-computed evidence about a single project — you do
NOT have access to raw issues. Assess ONLY schedule/timeline delivery risk.

Ground every finding in the supplied evidence. If the evidence is weak or
ambiguous, lower your confidence rather than inventing facts. Prefer a small
number of well-supported findings. If there is genuinely no material schedule
risk, return an empty list."""


def build_user_prompt(evidence: EvidencePackage) -> str:
    m = evidence.metrics
    observations = "\n".join(f"- {o}" for o in evidence.observations) or "- (none)"
    return f"""Project: {evidence.project_name} ({evidence.project_key})

Computed metrics:
- backlog growth (month-over-month): {m.backlog_growth:.0%}
- reopen rate: {m.reopen_rate:.0%}
- open blockers: {m.blocker_count}
- max dependency depth: {m.dependency_depth}
- total issues: {m.issue_count}
- open issues: {m.open_issue_count}

Deterministic observations:
{observations}

Produce schedule-risk findings. For each: probability (0-1), impact (0-1),
severity (low/medium/high/critical), confidence (0-1), a concise evidence-grounded
explanation, the assumptions you made, and concrete recommended mitigation actions."""
