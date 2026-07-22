"""Unit tests for the deterministic scenario mechanics (pure + fake Mongo).

Covers keyword effect estimation (capacity/scope/deadline signals, bounds),
cascade propagation via cross-project dependency links + shared contributors, and
the portfolio-risk-delta aggregation.
"""
from __future__ import annotations

from risk_analytics_api.services.scenario import cascade as cs
from tests.support.mongo import FakeMongo

_COLLECTIONS = {
    "issue_links": [
        # APACHE issues depending on BILLING (cross-project) + one internal link.
        {"project_key": "APACHE", "source_issue_key": "APACHE-1",
         "target_issue_key": "BILLING-9", "link_type": "blocks"},
        {"project_key": "APACHE", "source_issue_key": "APACHE-2",
         "target_issue_key": "BILLING-4", "link_type": "depends on"},
        {"project_key": "APACHE", "source_issue_key": "APACHE-3",
         "target_issue_key": "APACHE-8", "link_type": "blocks"},
    ],
    "issue_histories": [
        {"project_key": "APACHE", "author": "alice"},
        {"project_key": "APACHE", "author": "bob"},
        {"project_key": "BILLING", "author": "alice"},   # shared with APACHE
        {"project_key": "PAYMENTS", "author": "carol"},  # no overlap
    ],
}


def _db():
    return FakeMongo(_COLLECTIONS).db()


def test_effect_add_capacity_is_positive_and_scales() -> None:
    one = cs.estimate_scenario_effect("add 1 engineer to the team")
    three = cs.estimate_scenario_effect("add 3 engineers to the team")
    assert one > 0 and three > one


def test_effect_move_people_away_is_negative() -> None:
    assert cs.estimate_scenario_effect("move 2 engineers to Payments") < 0


def test_effect_descope_positive_compress_negative() -> None:
    assert cs.estimate_scenario_effect("descope the reporting module") > 0
    assert cs.estimate_scenario_effect("accelerate to an earlier deadline") < 0


def test_effect_neutral_text_is_zero_and_bounded() -> None:
    assert cs.estimate_scenario_effect("keep everything the same") == 0.0
    huge = cs.estimate_scenario_effect("add 999 engineers and descope and extend")
    assert huge <= cs._MAX_ABS_DELTA


def test_cascade_finds_dependency_and_shared_contributor_targets() -> None:
    cascades = cs.find_cascades(_db(), "APACHE")
    by_key = {c["project_key"] for c in cascades}
    assert "BILLING" in by_key       # coupled via deps AND shared contributor
    assert "PAYMENTS" not in by_key   # no dependency, no shared contributor
    assert "APACHE" not in by_key     # never cascades to itself
    billing = next(c for c in cascades if c["project_key"] == "BILLING")
    # BILLING is coupled through both channels -> combined effect label.
    assert "capacity" in billing["effect"] and "slip" in billing["effect"]
    assert billing["magnitude"] in {"high", "medium", "low"}


def test_cascade_empty_when_no_coupling() -> None:
    db = FakeMongo({"issue_links": [], "issue_histories": [
        {"project_key": "SOLO", "author": "zed"}]}).db()
    assert cs.find_cascades(db, "SOLO") == []


def test_portfolio_risk_delta_rises_when_source_worsens_and_cascades_spill() -> None:
    cascades = [{"magnitude": "high"}, {"magnitude": "low"}]
    # source got worse (probability_delta negative) -> portfolio risk up.
    worse = cs.portfolio_risk_delta(-0.1, cascades)
    better = cs.portfolio_risk_delta(0.1, cascades)
    assert worse > better
    assert worse > 0
