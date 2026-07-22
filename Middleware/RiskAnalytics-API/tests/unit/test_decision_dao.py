"""Behavioural tests for the PostgreSQL decision DAO (fake pg, no real DB).

Round-trip, the select/approve UPDATE transitions, scope filtering, case-insensitive
search (project_key/narrative), newest-first ordering, pagination, uuid->str, the
derived option_count, and the 100-row history cap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_analytics_api.daos.decisions import PostgresDecisionDao
from risk_analytics_api.dtos.responses import DecisionOption, DecisionRecord
from tests.support.pg_decisions import fake_decision_db

_BASE = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _option(oid="opt-1", **kw):
    base = dict(option_id=oid, title="Reprioritize", summary="s",
                actions=["a1", "a2"], suggested_owners=["alice"],
                predicted_outcome="better", tradeoffs="cost",
                recovery_estimate="2 weeks", confidence=0.7)
    base.update(kw)
    return DecisionOption(**base)


def _record(did, *, project_key="APACHE", requested_by=None, narrative="stabilize",
            status="DRAFTED", options=None, minute=0) -> DecisionRecord:
    return DecisionRecord(
        decision_id=did, project_key=project_key, requested_by=requested_by,
        status=status,
        options=options if options is not None else [_option("opt-1"), _option("opt-2")],
        selected_option_id=None, narrative=narrative, confidence=0.66,
        run_id="run-" + did, created_at=_BASE + timedelta(minutes=minute), approved_at=None,
    )


def test_insert_then_get_round_trips_full_row() -> None:
    dao = PostgresDecisionDao(fake_decision_db())
    dao.insert_decision(_record("d1", narrative="blockers dominate"))
    got = dao.get_decision("d1")
    assert got is not None
    assert got.decision_id == "d1" and got.project_key == "APACHE"
    assert got.status == "DRAFTED" and got.selected_option_id is None
    assert got.question is None and got.approved_at is None
    assert [o.option_id for o in got.options] == ["opt-1", "opt-2"]
    assert got.options[0].actions == ["a1", "a2"]
    assert got.options[0].suggested_owners == ["alice"]
    assert got.run_id == "run-d1"


def test_get_missing_returns_none() -> None:
    assert PostgresDecisionDao(fake_decision_db()).get_decision("nope") is None


def test_update_selection_transitions_state() -> None:
    dao = PostgresDecisionDao(fake_decision_db())
    dao.insert_decision(_record("d1"))
    dao.update_selection("d1", "opt-2", "SELECTED")
    got = dao.get_decision("d1")
    assert got.status == "SELECTED" and got.selected_option_id == "opt-2"


def test_update_approval_sets_status_and_timestamp() -> None:
    dao = PostgresDecisionDao(fake_decision_db())
    dao.insert_decision(_record("d1"))
    dao.update_selection("d1", "opt-1", "SELECTED")
    approved = _BASE + timedelta(hours=1)
    dao.update_approval("d1", "APPROVED", approved)
    got = dao.get_decision("d1")
    assert got.status == "APPROVED" and got.approved_at == approved
    assert got.selected_option_id == "opt-1"


def test_list_newest_first_with_option_count() -> None:
    dao = PostgresDecisionDao(fake_decision_db())
    for i, minute in enumerate([0, 10, 5]):
        dao.insert_decision(_record(f"d{i}", minute=minute))
    page = dao.list_decisions(scope=None, q=None, limit=20, offset=0)
    assert page.total == 3
    assert [it.decision_id for it in page.items] == ["d1", "d2", "d0"]
    assert page.items[0].option_count == 2


def test_scope_filters_by_requested_by() -> None:
    dao = PostgresDecisionDao(fake_decision_db())
    dao.insert_decision(_record("a", requested_by="alice", minute=1))
    dao.insert_decision(_record("b", requested_by="bob", minute=2))
    page = dao.list_decisions(scope="alice", q=None, limit=20, offset=0)
    assert [it.decision_id for it in page.items] == ["a"]


def test_search_is_case_insensitive_over_project_and_narrative() -> None:
    dao = PostgresDecisionDao(fake_decision_db())
    dao.insert_decision(_record("a", project_key="APACHE", narrative="blocker triage", minute=1))
    dao.insert_decision(_record("b", project_key="BILLING", narrative="add capacity", minute=2))
    assert [it.decision_id for it in
            dao.list_decisions(None, "BLOCKER", 20, 0).items] == ["a"]
    assert [it.decision_id for it in
            dao.list_decisions(None, "billing", 20, 0).items] == ["b"]


def test_pagination_offset_and_limit() -> None:
    dao = PostgresDecisionDao(fake_decision_db())
    for i in range(5):
        dao.insert_decision(_record(f"d{i}", minute=i))
    page = dao.list_decisions(scope=None, q=None, limit=2, offset=1)
    # newest-first: d4, d3, d2, d1, d0 -> offset 1, limit 2 -> d3, d2
    assert [it.decision_id for it in page.items] == ["d3", "d2"]


def test_history_capped_at_100() -> None:
    dao = PostgresDecisionDao(fake_decision_db())
    for i in range(120):
        dao.insert_decision(_record(f"d{i:03d}", minute=i))
    page = dao.list_decisions(scope=None, q=None, limit=100, offset=0)
    assert page.total == 100 and len(page.items) == 100


def test_uuid_pk_cast_to_str_in_mappers() -> None:
    import uuid

    # pg8000 returns the uuid PK as a UUID object — seed the store the same way
    # (bypassing the DTO) so the mappers' str() cast is genuinely exercised.
    real = uuid.uuid4()
    seed = {
        "decision_id": real, "project_key": "APACHE", "requested_by": None,
        "status": "DRAFTED", "options": [_option("opt-1").model_dump()],
        "selected_option_id": None, "narrative": "n", "confidence": 0.5,
        "run_id": "r", "created_at": _BASE, "approved_at": None,
    }
    dao = PostgresDecisionDao(fake_decision_db(rows=[seed]))
    got = dao.get_decision(real)
    assert isinstance(got.decision_id, str) and got.decision_id == str(real)
    page = dao.list_decisions(scope=None, q=None, limit=20, offset=0)
    assert isinstance(page.items[0].decision_id, str)
