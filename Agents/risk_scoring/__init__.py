"""Risk Scoring processor (deterministic — no LLM).

Ranks the finding set by score and stamps a portfolio priority order into each
finding's ``meta``. Deterministic by design: scoring is an observable fact, not
a judgement, so no framework/LLM is involved (see the three-tier principle in
CLAUDE.md).
"""
from __future__ import annotations

from agent_core import FindingProcessor, ReviewContext, RiskFinding

AGENT_KEY = "risk_scoring"


class RiskScoringProcessor(FindingProcessor):
    agent_key = AGENT_KEY

    def process(self, context: ReviewContext) -> list[RiskFinding]:
        ordered = sorted(
            context.findings,
            key=lambda f: (f.score, f.probability * f.impact, f.confidence),
            reverse=True,
        )
        ranked: list[RiskFinding] = []
        for i, f in enumerate(ordered, start=1):
            ranked.append(f.model_copy(update={"meta": {**f.meta, "priority_rank": i}}))
        return ranked


def build(*_args, **_kwargs) -> RiskScoringProcessor:
    """Factory (signature-compatible with the LLM agents' build())."""
    return RiskScoringProcessor()
