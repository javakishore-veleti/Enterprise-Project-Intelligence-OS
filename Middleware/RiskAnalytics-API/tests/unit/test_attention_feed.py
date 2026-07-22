"""Unit tests for the attention service with a fake DAO (no DB, no clock)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from risk_analytics_api.dtos.responses import AttentionFindingRow
from risk_analytics_api.interfaces.daos import AttentionDao
from risk_analytics_api.services.attention import DefaultAttentionService, attention_score

_NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _row(
    fid: str,
    *,
    project_key: str = "APACHE",
    severity: str = "HIGH",
    probability: float = 1.0,
    confidence: float | None = 1.0,
    ts: datetime | None = None,
    actions: list[str] | None = None,
    explanation: str = "x",
) -> AttentionFindingRow:
    return AttentionFindingRow(
        finding_id=fid, run_id="run-1", project_key=project_key, agent_key="schedule_risk",
        risk_category="schedule", severity=severity, score=42.0, probability=probability,
        confidence=confidence, explanation=explanation,
        recommended_actions=actions or [], analysis_timestamp=ts or _NOW,
    )


class FakeAttentionDao(AttentionDao):
    def __init__(self, rows: list[AttentionFindingRow]):
        # Stored newest-first, as the SQL ORDER BY DESC would return.
        self._rows = sorted(rows, key=lambda r: r.analysis_timestamp, reverse=True)
        self.window_calls: list[tuple] = []
        self.count_calls: list[tuple] = []
        self.distinct_calls: list[tuple] = []

    def count(self, as_of_end, projects):
        self.count_calls.append((as_of_end, projects))
        rows = self._filtered(as_of_end, projects)
        return len(rows)

    def distinct_projects(self, as_of_end, projects):
        self.distinct_calls.append((as_of_end, projects))
        rows = self._filtered(as_of_end, projects)
        return len({r.project_key for r in rows})

    def window(self, as_of_end, projects, cap):
        self.window_calls.append((as_of_end, projects, cap))
        return self._filtered(as_of_end, projects)[:cap]

    def _filtered(self, as_of_end, projects):
        rows = self._rows
        if as_of_end is not None:
            rows = [r for r in rows if r.analysis_timestamp < as_of_end]
        if projects is not None:
            rows = [r for r in rows if r.project_key in projects]
        return rows


def _feed(service, **kw):
    params = dict(top=10, offset=0, as_of=None, as_of_end=None, projects=None, now=_NOW)
    params.update(kw)
    return service.feed(**params)


def test_attention_score_bounds_and_max() -> None:
    # CRITICAL, prob=1, conf=1, ts=now -> exactly 100.
    row = _row("f", severity="CRITICAL", probability=1.0, confidence=1.0, ts=_NOW)
    assert attention_score(row, _NOW) == pytest.approx(100.0)


def test_attention_score_formula_components() -> None:
    # HIGH(0.8) * (0.5+0.5*0.4) * 0.5 * (0.4+0.6*recency); ts=now -> recency 1.
    row = _row("f", severity="HIGH", probability=0.4, confidence=0.5, ts=_NOW)
    expected = 100.0 * 0.8 * (0.5 + 0.5 * 0.4) * 0.5 * 1.0
    assert attention_score(row, _NOW) == pytest.approx(expected)


def test_attention_score_within_range_for_old_and_future() -> None:
    old = _row("f", ts=_NOW - timedelta(days=400))
    future = _row("f", ts=_NOW + timedelta(days=10))
    for r in (old, future):
        s = attention_score(r, _NOW)
        assert 0.0 <= s <= 100.0


def test_missing_confidence_defaults_to_0_6() -> None:
    row = _row("f", severity="CRITICAL", probability=1.0, confidence=None, ts=_NOW)
    # 100 * 1 * 1 * 0.6 * 1 = 60.
    assert attention_score(row, _NOW) == pytest.approx(60.0)
    service = DefaultAttentionService(FakeAttentionDao([row]))
    item = _feed(service).items[0]
    assert item.confidence == pytest.approx(0.6)


def test_unknown_severity_uses_default_weight() -> None:
    row = _row("f", severity="weird", probability=1.0, confidence=1.0, ts=_NOW)
    # default sev weight 0.4 -> 100 * 0.4 * 1 * 1 * 1 = 40.
    assert attention_score(row, _NOW) == pytest.approx(40.0)


def test_ordering_by_attention_score_desc() -> None:
    rows = [
        _row("low", severity="LOW", ts=_NOW),
        _row("crit", severity="CRITICAL", ts=_NOW),
        _row("med", severity="MEDIUM", ts=_NOW),
    ]
    service = DefaultAttentionService(FakeAttentionDao(rows))
    items = _feed(service).items
    assert [i.finding_id for i in items] == ["crit", "med", "low"]
    scores = [i.attention_score for i in items]
    assert scores == sorted(scores, reverse=True)


def test_tie_break_timestamp_desc_then_finding_id() -> None:
    # Same severity/prob/conf but different timestamps -> newer first.
    rows = [
        _row("b", severity="HIGH", ts=_NOW - timedelta(days=1)),
        _row("a", severity="HIGH", ts=_NOW),
    ]
    service = DefaultAttentionService(FakeAttentionDao(rows))
    items = _feed(service).items
    assert [i.finding_id for i in items] == ["a", "b"]

    # Fully identical (same ts) -> finding_id ascending.
    same_ts = [_row("z", ts=_NOW), _row("a", ts=_NOW), _row("m", ts=_NOW)]
    service2 = DefaultAttentionService(FakeAttentionDao(same_ts))
    items2 = _feed(service2).items
    assert [i.finding_id for i in items2] == ["a", "m", "z"]


def test_offset_and_top_paging_after_sort() -> None:
    rows = [_row(f"f{i}", severity="HIGH", ts=_NOW - timedelta(days=i)) for i in range(5)]
    service = DefaultAttentionService(FakeAttentionDao(rows))
    page = _feed(service, top=2, offset=1)
    # Sorted newest-first: f0,f1,f2,f3,f4 -> offset 1, top 2 -> f1,f2.
    assert [i.finding_id for i in page.items] == ["f1", "f2"]
    assert page.returned == 2
    assert page.total == 5  # total is the full in-scope count, not the page.


def test_as_of_filter_passthrough_and_echo() -> None:
    dao = FakeAttentionDao([_row("f", ts=_NOW)])
    service = DefaultAttentionService(dao)
    as_of_end = datetime(2026, 7, 21, tzinfo=timezone.utc)
    resp = _feed(service, as_of="2026-07-20", as_of_end=as_of_end)
    assert resp.as_of == "2026-07-20"
    assert dao.window_calls[0][0] == as_of_end
    assert dao.count_calls[0][0] == as_of_end


def test_scope_projects_minus_one_when_unscoped() -> None:
    dao = FakeAttentionDao([_row("f", project_key="APACHE"), _row("g", project_key="SPARK")])
    service = DefaultAttentionService(dao)
    resp = _feed(service)
    assert resp.scope_projects == -1
    assert dao.distinct_calls == []  # never queried when unscoped


def test_scope_projects_counts_distinct_when_scoped() -> None:
    rows = [
        _row("f", project_key="APACHE"),
        _row("g", project_key="SPARK"),
        _row("h", project_key="APACHE"),
    ]
    dao = FakeAttentionDao(rows)
    service = DefaultAttentionService(dao)
    resp = _feed(service, projects=["APACHE", "SPARK"])
    assert resp.scope_projects == 2
    assert resp.total == 3


def test_empty_feed() -> None:
    service = DefaultAttentionService(FakeAttentionDao([]))
    resp = _feed(service)
    assert resp.items == []
    assert resp.returned == 0
    assert resp.total == 0


def test_explanation_trimmed_and_actions_passthrough() -> None:
    row = _row("f", explanation="y" * 500, actions=["mitigate", "escalate"])
    service = DefaultAttentionService(FakeAttentionDao([row]))
    item = _feed(service).items[0]
    assert len(item.explanation) == 240
    assert item.recommended_actions == ["mitigate", "escalate"]
