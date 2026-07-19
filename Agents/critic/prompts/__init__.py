"""Prompts for the critic processor."""
from __future__ import annotations

from agent_core import ReviewContext

SYSTEM_PROMPT = """You are an adversarial critic of risk findings. Your job is to
challenge weak, redundant, or overstated findings so only well-founded risks
survive. For each finding you review, decide a verdict: 'keep', 'weaken' (keep
but lower confidence), or 'drop' (remove — unfounded or duplicative). Provide a
one-line critique per finding. Be skeptical but do not drop genuinely
evidence-grounded risks."""


def build_user_prompt(context: ReviewContext) -> str:
    findings = "\n".join(
        f"[{i}] ({f.risk_category.value}, score={f.score}, conf={f.confidence}) {f.explanation}"
        for i, f in enumerate(context.findings)
    )
    return f"""Project: {context.project_name} ({context.project_key})

Findings under review:
{findings}

Return one verdict per finding index: verdict in {{keep, weaken, drop}} and a
short critique."""
