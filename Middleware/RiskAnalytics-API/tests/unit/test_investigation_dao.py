"""Behavioural tests for the PostgreSQL investigation DAO (fake pg, no real DB).

Covers the round-trip (insert -> get), scope filtering, case-insensitive search,
newest-first ordering, pagination, and the 100-row history cap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_analytics_api.daos.investigations import PostgresInvestigationDao
from risk_analytics_api.dtos.responses import (
    EvidenceCitation,
    InvestigationRecord,
    InvestigationStep,
)
from tests.support.pg import FakePostgresDatabase

_BASE = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _record(
    inv_id: str, *, project_key="APACHE", requested_by=None, question=None,
    root_cause="cause", status="COMPLETED", minute=0,
) -> InvestigationRecord:
    return InvestigationRecord(
        investigation_id=inv_id, project_key=project_key, requested_by=requested_by,
        question=question, template_key="full", status=status, root_cause=root_cause,
        confidence=0.7, recommended_action="do it", hypotheses=["h1"],
        causal_chain=["a", "b"],
        steps=[InvestigationStep(action="metrics_snapshot()", observation="{}", hypothesis="h1")],
        evidence=[EvidenceCitation(kind="metrics_snapshot", detail="ok", count=None)],
        run_id="run-" + inv_id, created_at=_BASE + timedelta(minutes=minute),
    )


def test_insert_then_get_round_trips_full_row() -> None:
    db = FakePostgresDatabase()
    dao = PostgresInvestigationDao(db)
    dao.insert_investigation(_record("i1", question="why slipping?"))

    got = dao.get_investigation("i1")
    assert got is not None
    assert got.investigation_id == "i1"
    assert got.project_key == "APACHE"
    assert got.template_key == "full"
    assert got.status == "COMPLETED"
    assert got.root_cause == "cause"
    assert got.hypotheses == ["h1"]
    assert got.causal_chain == ["a", "b"]
    assert [s.action for s in got.steps] == ["metrics_snapshot()"]
    assert [e.kind for e in got.evidence] == ["metrics_snapshot"]
    assert got.run_id == "run-i1"


def test_get_missing_returns_none() -> None:
    dao = PostgresInvestigationDao(FakePostgresDatabase())
    assert dao.get_investigation("nope") is None


def test_list_is_newest_first() -> None:
    db = FakePostgresDatabase()
    dao = PostgresInvestigationDao(db)
    for i, minute in enumerate([0, 10, 5]):
        dao.insert_investigation(_record(f"i{i}", minute=minute))

    page = dao.list_investigations(scope=None, q=None, limit=20, offset=0)
    assert page.total == 3 and page.returned == 3
    assert [it.investigation_id for it in page.items] == ["i1", "i2", "i0"]  # 10,5,0 min


def test_scope_filters_by_requested_by() -> None:
    db = FakePostgresDatabase()
    dao = PostgresInvestigationDao(db)
    dao.insert_investigation(_record("a", requested_by="alice", minute=1))
    dao.insert_investigation(_record("b", requested_by="bob", minute=2))

    page = dao.list_investigations(scope="alice", q=None, limit=20, offset=0)
    assert [it.investigation_id for it in page.items] == ["a"]
    assert page.total == 1


def test_q_searches_case_insensitively_across_fields() -> None:
    db = FakePostgresDatabase()
    dao = PostgresInvestigationDao(db)
    dao.insert_investigation(_record("p", project_key="PAYMENTS", root_cause="x", minute=1))
    dao.insert_investigation(_record("q", question="Why is BILLING late?", root_cause="x", minute=2))
    dao.insert_investigation(_record("r", root_cause="Reopen churn dominates", minute=3))

    by_project = dao.list_investigations(scope=None, q="payments", limit=20, offset=0)
    assert [it.investigation_id for it in by_project.items] == ["p"]

    by_question = dao.list_investigations(scope=None, q="billing", limit=20, offset=0)
    assert [it.investigation_id for it in by_question.items] == ["q"]

    by_cause = dao.list_investigations(scope=None, q="reopen", limit=20, offset=0)
    assert [it.investigation_id for it in by_cause.items] == ["r"]


def test_pagination_limit_and_offset() -> None:
    db = FakePostgresDatabase()
    dao = PostgresInvestigationDao(db)
    for i in range(5):
        dao.insert_investigation(_record(f"i{i}", minute=i))  # i4 newest

    page = dao.list_investigations(scope=None, q=None, limit=2, offset=1)
    assert page.total == 5
    assert page.limit == 2 and page.offset == 1 and page.returned == 2
    # newest-first is i4,i3,i2,i1,i0; offset 1 -> i3,i2
    assert [it.investigation_id for it in page.items] == ["i3", "i2"]


def test_history_capped_at_100() -> None:
    db = FakePostgresDatabase()
    dao = PostgresInvestigationDao(db)
    for i in range(130):
        dao.insert_investigation(_record(f"i{i:03d}", minute=i))

    page = dao.list_investigations(scope=None, q=None, limit=100, offset=0)
    assert page.total == 100  # LEAST(130, 100)
    assert page.returned == 100

    # Cannot page past the newest 100.
    beyond = dao.list_investigations(scope=None, q=None, limit=50, offset=100)
    assert beyond.returned == 0
