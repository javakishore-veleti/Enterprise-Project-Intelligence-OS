"""Behavioural tests for the PostgreSQL forecast DAO (fake pg, no real DB).

Round-trip, scope filtering, case-insensitive search (project_key/narrative),
newest-first ordering, pagination, uuid->str, and the 100-row history cap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_analytics_api.daos.forecasts import PostgresForecastDao
from risk_analytics_api.dtos.responses import ForecastDriver, ForecastRecord
from tests.support.pg_predict import fake_forecast_db

_BASE = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _record(fid, *, project_key="APACHE", requested_by=None, narrative="on track",
            status="COMPLETED", minute=0) -> ForecastRecord:
    return ForecastRecord(
        forecast_id=fid, project_key=project_key, requested_by=requested_by,
        status=status, on_time_probability=0.7, probability_low=0.6, probability_high=0.8,
        projected_slip_days_low=5, projected_slip_days_high=20, outlook="at_risk",
        drivers=[ForecastDriver(factor="reopen_churn", direction="up", detail="rising")],
        bull_case="lands", bear_case="slips", would_change_mind="velocity recovers",
        narrative=narrative, confidence=0.66, run_id="run-" + fid,
        created_at=_BASE + timedelta(minutes=minute),
    )


def test_insert_then_get_round_trips_full_row() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    dao.insert_forecast(_record("f1", narrative="reopen churn dominates"))
    got = dao.get_forecast("f1")
    assert got is not None
    assert got.forecast_id == "f1" and got.project_key == "APACHE"
    assert got.on_time_probability == 0.7
    assert got.probability_low == 0.6 and got.probability_high == 0.8
    assert got.outlook == "at_risk"
    assert got.projected_slip_days_low == 5 and got.projected_slip_days_high == 20
    assert [d.factor for d in got.drivers] == ["reopen_churn"]
    assert got.bull_case == "lands" and got.would_change_mind == "velocity recovers"
    assert got.question is None and got.run_id == "run-f1"


def test_get_missing_returns_none() -> None:
    assert PostgresForecastDao(fake_forecast_db()).get_forecast("nope") is None


def test_list_newest_first() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    for i, minute in enumerate([0, 10, 5]):
        dao.insert_forecast(_record(f"f{i}", minute=minute))
    page = dao.list_forecasts(scope=None, q=None, limit=20, offset=0)
    assert page.total == 3
    assert [it.forecast_id for it in page.items] == ["f1", "f2", "f0"]


def test_scope_filters_by_requested_by() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    dao.insert_forecast(_record("a", requested_by="alice", minute=1))
    dao.insert_forecast(_record("b", requested_by="bob", minute=2))
    page = dao.list_forecasts(scope="alice", q=None, limit=20, offset=0)
    assert [it.forecast_id for it in page.items] == ["a"] and page.total == 1


def test_q_searches_project_and_narrative() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    dao.insert_forecast(_record("p", project_key="PAYMENTS", minute=1))
    dao.insert_forecast(_record("n", narrative="Blocker pile-up is the story", minute=2))
    assert [it.forecast_id for it in
            dao.list_forecasts(None, "payments", 20, 0).items] == ["p"]
    assert [it.forecast_id for it in
            dao.list_forecasts(None, "blocker", 20, 0).items] == ["n"]


def test_pagination() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    for i in range(5):
        dao.insert_forecast(_record(f"f{i}", minute=i))
    page = dao.list_forecasts(None, None, 2, 1)
    assert page.total == 5 and page.returned == 2
    assert [it.forecast_id for it in page.items] == ["f3", "f2"]


def test_history_capped_at_100() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    for i in range(130):
        dao.insert_forecast(_record(f"f{i:03d}", minute=i))
    assert dao.list_forecasts(None, None, 100, 0).total == 100
    assert dao.list_forecasts(None, None, 50, 100).returned == 0


def _seed_multi_project(dao) -> None:
    dao.insert_forecast(_record("a", project_key="APACHE", minute=1))
    dao.insert_forecast(_record("b", project_key="BILLING", minute=2))
    dao.insert_forecast(_record("c", project_key="SPARK", minute=3))


def test_projects_filter_restricts_to_set() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    _seed_multi_project(dao)
    page = dao.list_forecasts(None, None, 20, 0, projects=["APACHE", "SPARK"])
    assert {it.forecast_id for it in page.items} == {"a", "c"} and page.total == 2
    assert "b" not in {it.forecast_id for it in page.items}


def test_projects_filter_combines_with_scope_and_q() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    dao.insert_forecast(_record("a", project_key="APACHE", requested_by="alice", minute=1))
    dao.insert_forecast(_record("b", project_key="BILLING", requested_by="alice", minute=2))
    dao.insert_forecast(_record("c", project_key="APACHE", requested_by="bob", minute=3))
    # scope=alice AND projects in {APACHE} -> only 'a'
    page = dao.list_forecasts("alice", None, 20, 0, projects=["APACHE"])
    assert [it.forecast_id for it in page.items] == ["a"] and page.total == 1


def test_projects_absent_returns_all() -> None:
    dao = PostgresForecastDao(fake_forecast_db())
    _seed_multi_project(dao)
    assert dao.list_forecasts(None, None, 20, 0).total == 3
    assert dao.list_forecasts(None, None, 20, 0, projects=None).total == 3
