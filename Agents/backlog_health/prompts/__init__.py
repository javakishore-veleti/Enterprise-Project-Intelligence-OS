"""Prompts for the backlog-health agent. Shared across all framework adapters."""
from __future__ import annotations

from agent_core import EvidencePackage

SYSTEM_PROMPT = """You are a backlog-health analyst for software delivery projects.
You are given deterministic, pre-computed evidence about a single project — you do
NOT have access to raw issues. Assess ONLY backlog health: whether the backlog is growing
faster than it is being burned down, the share of work left open, and whether reopened
issues are accumulating unresolved debt.

Ground every finding in the supplied evidence. If the evidence is weak, lower your
confidence rather than inventing facts. Prefer a small number of well-supported
findings. If there is genuinely no material backlog-health risk, return an empty list."""


def build_user_prompt(evidence: EvidencePackage) -> str:
    m = evidence.metrics
    observations = "\n".join(f"- {o}" for o in evidence.observations) or "- (none)"
    return f"""Project: {evidence.project_name} ({evidence.project_key})

Computed metrics:
- backlog growth (month-over-month): {m.backlog_growth:.0%}
- open issues: {m.open_issue_count} of {m.issue_count} total
- reopen rate: {m.reopen_rate:.0%}
- open blockers: {m.blocker_count}

Deterministic observations:
{observations}

Produce backlog-health findings. For each: probability (0-1), impact (0-1),
severity (low/medium/high/critical), confidence (0-1), a concise evidence-grounded
explanation, your assumptions, and concrete recommended remediation actions."""
