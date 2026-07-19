"""Hermetic tests for the deterministic review processors (no LLM)."""
from __future__ import annotations

from datetime import datetime, timezone

from agent_core import (
    EvidenceMetrics,
    EvidencePackage,
    ReviewContext,
    RiskCategory,
    RiskFinding,
    Severity,
)
from risk_correlation import RiskCorrelationProcessor
from risk_deduplication import RiskDeduplicationProcessor
from risk_scoring import RiskScoringProcessor

_EVID = EvidencePackage(project_key="APACHE", project_name="Apache", metrics=EvidenceMetrics())


def _f(category, score, agent="a", conf=0.8) -> RiskFinding:
    return RiskFinding(
        risk_category=category, probability=0.6, impact=0.6, severity=Severity.MEDIUM,
        score=score, confidence=conf, explanation=f"{agent} {category.value} {score}",
        source_agent=agent, analysis_timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _ctx(findings) -> ReviewContext:
    return ReviewContext(project_key="APACHE", project_name="Apache", evidence=_EVID, findings=findings)


def test_scoring_ranks_by_score_desc_and_stamps_rank() -> None:
    out = RiskScoringProcessor().process(_ctx([
        _f(RiskCategory.SCHEDULE, 30), _f(RiskCategory.QUALITY, 60), _f(RiskCategory.BACKLOG, 45),
    ]))
    assert [f.score for f in out] == [60, 45, 30]
    assert [f.meta["priority_rank"] for f in out] == [1, 2, 3]


def test_dedup_merges_same_category_within_band() -> None:
    out = RiskDeduplicationProcessor().process(_ctx([
        _f(RiskCategory.SCHEDULE, 50, "schedule_risk"),
        _f(RiskCategory.SCHEDULE, 45, "backlog_health"),  # within 20 band -> merged
        _f(RiskCategory.QUALITY, 40, "quality_risk"),
    ]))
    cats = sorted(f.risk_category.value for f in out)
    assert cats == ["quality", "schedule"]  # two schedule findings merged into one
    merged = next(f for f in out if f.risk_category is RiskCategory.SCHEDULE)
    assert merged.meta["merged_count"] == 2
    assert set(merged.meta["merged_from"]) == {"schedule_risk", "backlog_health"}


def test_dedup_keeps_distant_scores_separate() -> None:
    out = RiskDeduplicationProcessor().process(_ctx([
        _f(RiskCategory.SCHEDULE, 80), _f(RiskCategory.SCHEDULE, 20),  # 60 apart -> not merged
    ]))
    assert len(out) == 2


def test_correlation_groups_same_category() -> None:
    out = RiskCorrelationProcessor().process(_ctx([
        _f(RiskCategory.SCHEDULE, 50, "a"), _f(RiskCategory.SCHEDULE, 30, "b"),
        _f(RiskCategory.QUALITY, 40, "c"),
    ]))
    sched = [f for f in out if f.risk_category is RiskCategory.SCHEDULE]
    qual = [f for f in out if f.risk_category is RiskCategory.QUALITY]
    assert all("correlation_group" in f.meta for f in sched)
    assert sched[0].meta["correlation_size"] == 2
    assert "correlation_group" not in qual[0].meta  # singletons are not correlated


def test_processors_handle_empty() -> None:
    for proc in (RiskScoringProcessor(), RiskDeduplicationProcessor(), RiskCorrelationProcessor()):
        assert proc.process(_ctx([])) == []
