"""Prompts for the evidence-validation processor."""
from __future__ import annotations

from agent_core import ReviewContext

SYSTEM_PROMPT = """You are an evidence-validation reviewer. You are given the
deterministic evidence for a project and a list of candidate risk findings
produced by specialist agents. For each finding, decide whether it is genuinely
SUPPORTED by the evidence provided (not speculation beyond the evidence).

Be strict but fair: a finding is supported if the evidence plausibly grounds it.
If a finding overreaches or is not backed by the metrics/observations, mark it
unsupported. Adjust confidence down when support is weak. Return exactly one
verdict per finding, referencing its index."""


def build_user_prompt(context: ReviewContext) -> str:
    m = context.evidence.metrics
    obs = "\n".join(f"- {o}" for o in context.evidence.observations) or "- (none)"
    findings = "\n".join(
        f"[{i}] ({f.risk_category.value}, score={f.score}, conf={f.confidence}) {f.explanation}"
        for i, f in enumerate(context.findings)
    )
    return f"""Project: {context.project_name} ({context.project_key})

Evidence metrics: backlog_growth={m.backlog_growth:.0%}, reopen_rate={m.reopen_rate:.0%}, \
blockers={m.blocker_count}, dependency_depth={m.dependency_depth}, \
issues={m.issue_count}, open={m.open_issue_count}
Observations:
{obs}

Candidate findings:
{findings}

For each finding index, return supported (bool), adjusted_confidence (0-1), and a
short note explaining the validation decision."""
