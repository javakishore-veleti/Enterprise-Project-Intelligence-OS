"""Behavioural tests for the PostgreSQL scenario DAO (fake pg, no real DB).

Round-trip, scope filtering, case-insensitive search (project_key/scenario/
narrative), newest-first ordering, pagination, uuid->str, and the 100-row cap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_analytics_api.daos.scenarios import PostgresScenarioDao
from risk_analytics_api.dtos.responses import ScenarioCascade, ScenarioRecord
from tests.support.pg_predict import fake_scenario_db

_BASE = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _record(sid, *, project_key="APACHE", requested_by=None, scenario="move 2 engineers",
            narrative="trade-off", status="COMPLETED", minute=0) -> ScenarioRecord:
    return ScenarioRecord(
        scenario_id=sid, project_key=project_key, requested_by=requested_by,
        scenario=scenario, status=status, base_on_time_probability=0.7,
        projected_on_time_probability=0.58, probability_delta=-0.12,
        base_slip_days=10, projected_slip_days=25, portfolio_risk_delta=0.27,
        cascades=[ScenarioCascade(project_key="BILLING", effect="delivery slip risk",
                                  reason="deps", magnitude="high")],
        narrative=narrative, confidence=0.6, run_id="run-" + sid,
        created_at=_BASE + timedelta(minutes=minute),
    )


def test_insert_then_get_round_trips_full_row() -> None:
    dao = PostgresScenarioDao(fake_scenario_db())
    dao.insert_scenario(_record("s1"))
    got = dao.get_scenario("s1")
    assert got is not None
    assert got.scenario_id == "s1" and got.project_key == "APACHE"
    assert got.scenario == "move 2 engineers"
    assert got.base_on_time_probability == 0.7
    assert got.projected_on_time_probability == 0.58
    assert got.probability_delta == -0.12
    assert got.base_slip_days == 10 and got.projected_slip_days == 25
    assert got.portfolio_risk_delta == 0.27
    assert [c.project_key for c in got.cascades] == ["BILLING"]
    assert got.cascades[0].magnitude == "high"
    assert got.run_id == "run-s1"


def test_get_missing_returns_none() -> None:
    assert PostgresScenarioDao(fake_scenario_db()).get_scenario("nope") is None


def test_list_newest_first() -> None:
    dao = PostgresScenarioDao(fake_scenario_db())
    for i, minute in enumerate([0, 10, 5]):
        dao.insert_scenario(_record(f"s{i}", minute=minute))
    page = dao.list_scenarios(None, None, 20, 0)
    assert [it.scenario_id for it in page.items] == ["s1", "s2", "s0"]


def test_scope_filters_by_requested_by() -> None:
    dao = PostgresScenarioDao(fake_scenario_db())
    dao.insert_scenario(_record("a", requested_by="alice", minute=1))
    dao.insert_scenario(_record("b", requested_by="bob", minute=2))
    assert [it.scenario_id for it in
            dao.list_scenarios("alice", None, 20, 0).items] == ["a"]


def test_q_searches_project_scenario_and_narrative() -> None:
    dao = PostgresScenarioDao(fake_scenario_db())
    dao.insert_scenario(_record("p", project_key="PAYMENTS", minute=1))
    dao.insert_scenario(_record("s", scenario="descope the billing module", minute=2))
    dao.insert_scenario(_record("n", narrative="cascade hits BILLING hard", minute=3))
    assert [it.scenario_id for it in dao.list_scenarios(None, "payments", 20, 0).items] == ["p"]
    assert [it.scenario_id for it in dao.list_scenarios(None, "descope", 20, 0).items] == ["s"]
    assert [it.scenario_id for it in dao.list_scenarios(None, "cascade", 20, 0).items] == ["n"]


def test_pagination() -> None:
    dao = PostgresScenarioDao(fake_scenario_db())
    for i in range(5):
        dao.insert_scenario(_record(f"s{i}", minute=i))
    page = dao.list_scenarios(None, None, 2, 1)
    assert [it.scenario_id for it in page.items] == ["s3", "s2"]


def test_history_capped_at_100() -> None:
    dao = PostgresScenarioDao(fake_scenario_db())
    for i in range(130):
        dao.insert_scenario(_record(f"s{i:03d}", minute=i))
    assert dao.list_scenarios(None, None, 100, 0).total == 100
    assert dao.list_scenarios(None, None, 50, 100).returned == 0
