"""Attention service: deterministically score, sort, and paginate findings.

The DAO returns a bounded, newest-first window already filtered by scope +
as_of; this service assigns each finding an ``attention_score`` in [0, 100],
sorts, and slices to ``offset``/``top``. The reference instant ``now`` is
injected (never read from the clock here) so scoring stays testable.
"""
from __future__ import annotations

from datetime import datetime, timezone

from risk_analytics_api.dtos.responses import (
    AttentionFindingRow,
    AttentionItem,
    AttentionResponse,
)
from risk_analytics_api.interfaces.daos import AttentionDao
from risk_analytics_api.interfaces.services import AttentionService

#: Cap on the newest-first window the DAO scores (keeps scoring bounded across
#: dozens of projects). ``total`` still reflects the true in-scope count.
WINDOW_CAP = 500

#: Explanation length surfaced in the feed.
_EXPLANATION_MAX = 240

_SEVERITY_WEIGHT = {"CRITICAL": 1.0, "HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.25}
_DEFAULT_SEVERITY_WEIGHT = 0.4
_DEFAULT_CONFIDENCE = 0.6


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _recency(age_days: float) -> float:
    """Linear approximation of exp(-age_days/30): fresh -> 1, ~2 months -> 0."""
    return _clamp01(1.0 - age_days / 60.0)


def attention_score(row: AttentionFindingRow, now: datetime) -> float:
    """Deterministic ranking score in [0, 100]."""
    sev_w = _SEVERITY_WEIGHT.get((row.severity or "").upper(), _DEFAULT_SEVERITY_WEIGHT)
    prob = _clamp01(row.probability)
    conf = _clamp01(row.confidence if row.confidence is not None else _DEFAULT_CONFIDENCE)
    ts = row.analysis_timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ref = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    age_days = (ref - ts).total_seconds() / 86400.0
    recency = _recency(age_days)
    return 100.0 * sev_w * (0.5 + 0.5 * prob) * conf * (0.4 + 0.6 * recency)


class DefaultAttentionService(AttentionService):
    def __init__(self, attention_dao: AttentionDao, window_cap: int = WINDOW_CAP) -> None:
        self._dao = attention_dao
        self._cap = window_cap

    def feed(
        self,
        *,
        top: int,
        offset: int,
        as_of: str | None,
        as_of_end: datetime | None,
        projects: list[str] | None,
        now: datetime,
    ) -> AttentionResponse:
        rows = self._dao.window(as_of_end, projects, self._cap)
        items = [self._to_item(r, now) for r in rows]

        # Sort: attention_score DESC, then analysis_timestamp DESC, then finding_id ASC.
        # Stable sort => apply the finding_id (ascending) key first.
        items.sort(key=lambda i: i.finding_id)
        items.sort(key=lambda i: (i.attention_score, i.analysis_timestamp), reverse=True)

        page = items[offset:offset + top]
        total = self._dao.count(as_of_end, projects)
        scope_projects = -1 if projects is None else self._dao.distinct_projects(as_of_end, projects)

        return AttentionResponse(
            as_of=as_of,
            scope_projects=scope_projects,
            total=total,
            returned=len(page),
            items=page,
        )

    def _to_item(self, row: AttentionFindingRow, now: datetime) -> AttentionItem:
        conf = row.confidence if row.confidence is not None else _DEFAULT_CONFIDENCE
        return AttentionItem(
            finding_id=row.finding_id,
            run_id=row.run_id,
            project_key=row.project_key,
            agent_key=row.agent_key,
            risk_category=row.risk_category,
            severity=row.severity,
            score=row.score,
            probability=row.probability,
            confidence=conf,
            attention_score=attention_score(row, now),
            explanation=(row.explanation or "")[:_EXPLANATION_MAX],
            recommended_actions=list(row.recommended_actions),
            analysis_timestamp=row.analysis_timestamp,
        )
