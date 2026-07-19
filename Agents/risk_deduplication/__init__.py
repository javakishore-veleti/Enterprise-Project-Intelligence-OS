"""Risk Deduplication processor (deterministic — no LLM).

Merges near-duplicate findings — the same underlying risk surfaced by more than
one detector. Heuristic: group by ``risk_category``; within a group, findings
whose scores fall in the same band are merged into the highest-scored
representative, unioning their recommended actions, assumptions, affected items,
and source agents. Deterministic and cheap.
"""
from __future__ import annotations

from agent_core import FindingProcessor, ReviewContext, RiskFinding

AGENT_KEY = "risk_deduplication"

_BAND = 20.0  # score-band width within which same-category findings are considered dupes


def _merge(primary: RiskFinding, others: list[RiskFinding]) -> RiskFinding:
    def _union(attr: str) -> list[str]:
        seen: list[str] = list(getattr(primary, attr))
        for o in others:
            for v in getattr(o, attr):
                if v not in seen:
                    seen.append(v)
        return seen

    sources = [primary.source_agent] + [o.source_agent for o in others]
    return primary.model_copy(update={
        "recommended_actions": _union("recommended_actions"),
        "assumptions": _union("assumptions"),
        "affected": _union("affected"),
        "meta": {**primary.meta, "merged_from": sources, "merged_count": len(sources)},
    })


class RiskDeduplicationProcessor(FindingProcessor):
    agent_key = AGENT_KEY

    def process(self, context: ReviewContext) -> list[RiskFinding]:
        by_category: dict[str, list[RiskFinding]] = {}
        for f in context.findings:
            by_category.setdefault(f.risk_category.value, []).append(f)

        result: list[RiskFinding] = []
        for group in by_category.values():
            group = sorted(group, key=lambda f: f.score, reverse=True)
            used = [False] * len(group)
            for i, primary in enumerate(group):
                if used[i]:
                    continue
                dupes = [
                    group[j] for j in range(i + 1, len(group))
                    if not used[j] and abs(group[j].score - primary.score) <= _BAND
                ]
                for j in range(i + 1, len(group)):
                    if not used[j] and abs(group[j].score - primary.score) <= _BAND:
                        used[j] = True
                result.append(_merge(primary, dupes) if dupes else primary)
        return result


def build(*_args, **_kwargs) -> RiskDeduplicationProcessor:
    return RiskDeduplicationProcessor()
