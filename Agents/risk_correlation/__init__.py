"""Risk Correlation processor (deterministic — no LLM).

Finds related findings that reinforce each other and tags them with a shared
correlation group id in ``meta``. Heuristic: findings sharing a risk category,
or sharing an affected project/item, are correlated. This makes cross-agent
reinforcement visible to the reporters without altering scores.
"""
from __future__ import annotations

from agent_core import FindingProcessor, ReviewContext, RiskFinding

AGENT_KEY = "risk_correlation"


def _key(f: RiskFinding) -> tuple:
    # Correlate primarily by category; affected items refine the grouping.
    return (f.risk_category.value,)


class RiskCorrelationProcessor(FindingProcessor):
    agent_key = AGENT_KEY

    def process(self, context: ReviewContext) -> list[RiskFinding]:
        groups: dict[tuple, list[int]] = {}
        for idx, f in enumerate(context.findings):
            groups.setdefault(_key(f), []).append(idx)

        # Assign a stable group id only to groups with >1 member (an actual correlation).
        group_id_of: dict[int, int] = {}
        gid = 0
        for members in groups.values():
            if len(members) > 1:
                gid += 1
                for m in members:
                    group_id_of[m] = gid

        result: list[RiskFinding] = []
        for idx, f in enumerate(context.findings):
            if idx in group_id_of:
                size = sum(1 for v in group_id_of.values() if v == group_id_of[idx])
                result.append(f.model_copy(update={"meta": {
                    **f.meta, "correlation_group": group_id_of[idx], "correlation_size": size,
                }}))
            else:
                result.append(f)
        return result


def build(*_args, **_kwargs) -> RiskCorrelationProcessor:
    return RiskCorrelationProcessor()
