"""Unit tests for the deterministic forecast math (pure, no LLM/infra).

Covers the on-time probability, the credible-interval bounds (variance-driven
half-width, ordering, clamping), the projected slip range, the outlook buckets,
and driver extraction (direction + ranking).
"""
from __future__ import annotations

from risk_analytics_api.services.forecast import forecasting as fc


def _snap(**kw) -> dict:
    base = dict(
        reopen_rate=0.0, blocker_count=0, backlog_growth=0.0, issue_aging_days=0.0,
        resolution_velocity=10.0, resolution_velocity_trend=0.0,
        contributor_concentration=0.0, critical_defect_ratio=0.0,
        computed_at="2026-02-01",
    )
    base.update(kw)
    return base


def test_health_score_healthy_project_is_high() -> None:
    p = fc.health_score(_snap())
    assert p >= 0.9


def test_health_score_penalizes_adverse_metrics() -> None:
    bad = _snap(reopen_rate=0.6, blocker_count=15, backlog_growth=0.5,
                issue_aging_days=120, critical_defect_ratio=0.4,
                contributor_concentration=0.7, resolution_velocity_trend=-8)
    assert fc.health_score(bad) < fc.health_score(_snap())
    assert 0.02 <= fc.health_score(bad) <= 0.98


def test_outlook_buckets() -> None:
    assert fc.outlook_for(0.8) == "on_track"
    assert fc.outlook_for(0.5) == "at_risk"
    assert fc.outlook_for(0.2) == "off_track"


def test_interval_halfwidth_widens_with_variance_and_is_bounded() -> None:
    steady = fc.interval_halfwidth([0.7, 0.7, 0.7])
    volatile = fc.interval_halfwidth([0.9, 0.3, 0.8, 0.2])
    assert volatile > steady
    assert fc._MIN_HALFWIDTH <= steady <= fc._MAX_HALFWIDTH
    assert fc._MIN_HALFWIDTH <= volatile <= fc._MAX_HALFWIDTH


def test_short_history_uses_wide_default_spread() -> None:
    assert fc.interval_halfwidth([0.7]) > fc.interval_halfwidth([0.7, 0.71, 0.7])


def test_compute_forecast_interval_ordered_and_clamped() -> None:
    history = [_snap(reopen_rate=0.3, blocker_count=5),
               _snap(reopen_rate=0.2, blocker_count=3),
               _snap(reopen_rate=0.1, blocker_count=1)]
    facts = fc.compute_forecast(history, {"issue_count": 100, "open_issue_count": 40})
    assert 0.0 <= facts.probability_low <= facts.on_time_probability <= facts.probability_high <= 1.0
    assert facts.projected_slip_days_low <= facts.projected_slip_days_high
    assert facts.projected_slip_days_low >= 0
    assert facts.trajectory_points == 3
    assert facts.outlook in {"on_track", "at_risk", "off_track"}


def test_slip_grows_as_probability_falls() -> None:
    snap = _snap()
    project = {"issue_count": 100, "open_issue_count": 50}
    assert fc.slip_center(0.2, snap, project) > fc.slip_center(0.9, snap, project)


def test_empty_history_is_neutral_and_maximally_uncertain() -> None:
    facts = fc.compute_forecast([], {"issue_count": 0, "open_issue_count": 0})
    assert facts.on_time_probability == 0.5
    assert facts.trajectory_points == 0
    assert facts.halfwidth == fc._MAX_HALFWIDTH
    assert facts.drivers == []


def test_drivers_extract_direction_and_rank() -> None:
    latest = _snap(blocker_count=12, reopen_rate=0.35, resolution_velocity_trend=-9,
                   backlog_growth=0.4, issue_aging_days=90)
    prior = _snap(blocker_count=2, reopen_rate=0.10, resolution_velocity_trend=0,
                  backlog_growth=0.0, issue_aging_days=30)
    drivers = fc.drivers_from(latest, prior)
    assert drivers  # something moved
    factors = {d["factor"]: d for d in drivers}
    # blockers piled up -> up; velocity trend negative -> down; backlog positive -> up.
    assert factors["blocker_burn_rate"]["direction"] == "up"
    assert factors["resolution_velocity"]["direction"] == "down"
    assert factors["backlog_growth"]["direction"] == "up"
    assert len(drivers) <= 5


def test_drivers_flat_when_nothing_moves() -> None:
    flat = _snap()
    assert fc.drivers_from(flat, flat) == []
