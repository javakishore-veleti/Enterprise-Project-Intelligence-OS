"""Unit tests for early-warning inflection detection + ranking (pure + fake Mongo).

Covers the biggest-adverse-move selection, direction/severity, the minimum
threshold, the <2-snapshot guard, and the service's cross-project ranking + scope.
"""
from __future__ import annotations

from risk_analytics_api.services.early_warning import DefaultEarlyWarningService
from risk_analytics_api.services.early_warning.inflection import detect_inflection
from tests.support.mongo import FakeMongo


def _snap(computed_at, **kw) -> dict:
    base = dict(
        reopen_rate=0.1, blocker_count=1, issue_aging_days=20.0, backlog_growth=0.0,
        resolution_velocity=10.0, contributor_concentration=0.2, critical_defect_ratio=0.05,
        computed_at=computed_at,
    )
    base.update(kw)
    return base


def test_detect_picks_biggest_adverse_move() -> None:
    # reopen_rate spiked hardest; blockers ticked up only slightly.
    history = [_snap("2026-03-01", reopen_rate=0.5, blocker_count=2),
               _snap("2026-02-01", reopen_rate=0.1, blocker_count=1)]
    inf = detect_inflection("APACHE", history)
    assert inf is not None
    assert inf.metric == "reopen_rate"
    assert inf.direction == "up"
    assert inf.from_value == 0.1 and inf.to_value == 0.5
    assert inf.severity in {"high", "medium", "low"}


def test_velocity_drop_is_adverse_down() -> None:
    history = [_snap("2026-03-01", resolution_velocity=2.0),
               _snap("2026-02-01", resolution_velocity=12.0)]
    inf = detect_inflection("APACHE", history)
    assert inf is not None and inf.metric == "resolution_velocity"
    assert inf.direction == "down"


def test_no_adverse_move_returns_none() -> None:
    # Everything improved or held steady.
    history = [_snap("2026-03-01", reopen_rate=0.05, blocker_count=0),
               _snap("2026-02-01", reopen_rate=0.1, blocker_count=1)]
    assert detect_inflection("APACHE", history) is None


def test_single_snapshot_returns_none() -> None:
    assert detect_inflection("APACHE", [_snap("2026-03-01")]) is None


_COLLECTIONS = {
    "project_metrics": [
        # APACHE: sharp reopen spike -> high severity.
        {"project_key": "APACHE", "computed_at": "2026-03-01", "reopen_rate": 0.55,
         "blocker_count": 2, "resolution_velocity": 10},
        {"project_key": "APACHE", "computed_at": "2026-02-01", "reopen_rate": 0.10,
         "blocker_count": 1, "resolution_velocity": 10},
        # BILLING: small blocker uptick -> low severity.
        {"project_key": "BILLING", "computed_at": "2026-03-01", "reopen_rate": 0.10,
         "blocker_count": 3, "resolution_velocity": 10},
        {"project_key": "BILLING", "computed_at": "2026-02-01", "reopen_rate": 0.10,
         "blocker_count": 2, "resolution_velocity": 10},
    ],
}


def test_service_ranks_most_severe_first() -> None:
    svc = DefaultEarlyWarningService(FakeMongo(_COLLECTIONS))
    resp = svc.warnings(scope=None, limit=10)
    keys = [w.project_key for w in resp.items]
    assert keys[0] == "APACHE"  # sharpest adverse move ranks first
    assert set(keys) == {"APACHE", "BILLING"}
    top = resp.items[0]
    assert top.metric == "reopen_rate" and top.severity == "high"
    assert top.window == "2026-02-01 to 2026-03-01"
    assert 0.0 <= top.confidence <= 1.0


def test_service_scope_filters_projects() -> None:
    svc = DefaultEarlyWarningService(FakeMongo(_COLLECTIONS))
    resp = svc.warnings(scope="APACHE", limit=10)
    assert {w.project_key for w in resp.items} == {"APACHE"}


def test_service_limit_caps_results() -> None:
    svc = DefaultEarlyWarningService(FakeMongo(_COLLECTIONS))
    assert len(svc.warnings(scope=None, limit=1).items) == 1
