"""Wiring tests for the decision service (fake Mongo, fake LLM, no infra).

Verifies the Decide seam: project check -> deterministic evidence (forecast facts +
top contributors) -> model resolution -> options agent (fake LLM) -> option-id
assignment + owner grounding + DTO assembly + DRAFTED persistence, then the
select/approve state transitions and list/get — with no real model call.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError, ValidationError
from risk_analytics_api.daos.decisions import PostgresDecisionDao
from risk_analytics_api.daos.evidence import MongoEvidenceDao
from risk_analytics_api.dtos.requests import DecisionRequest, SelectOptionRequest
from risk_analytics_api.dtos.responses import DecisionRecord
from risk_analytics_api.interfaces.daos import AgentConfigGateway, DecisionDao
from risk_analytics_api.services.decision import DefaultDecisionService
from tests.support.llm import FakeChatModel
from tests.support.mongo import FakeMongo
from tests.support.pg_decisions import fake_decision_db

COLLECTIONS = {
    "projects": [{"project_key": "APACHE", "name": "Apache",
                  "issue_count": 100, "open_issue_count": 40}],
    "project_metrics": [
        {"project_key": "APACHE", "computed_at": "2026-03-01", "reopen_rate": 0.4,
         "blocker_count": 8, "resolution_velocity": 6, "resolution_velocity_trend": -4},
        {"project_key": "APACHE", "computed_at": "2026-02-01", "reopen_rate": 0.2,
         "blocker_count": 3, "resolution_velocity": 10, "resolution_velocity_trend": 1},
    ],
    "issue_histories": [
        {"project_key": "APACHE", "author": "alice"},
        {"project_key": "APACHE", "author": "alice"},
        {"project_key": "APACHE", "author": "alice"},
        {"project_key": "APACHE", "author": "bob"},
    ],
}


def _option(title="Reprioritize blockers", actions=None, owners=None, **kw):
    base = dict(
        title=title, summary="what and when to pick it",
        actions=actions if actions is not None else ["Triage blockers", "Pair on the top driver"],
        suggested_owners=owners if owners is not None else [],
        predicted_outcome="Trajectory stabilizes", tradeoffs="Slows new feature work",
        recovery_estimate="2-4 weeks", confidence=0.7,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _decision(options=None, narrative="Prefer opt-1 unless capacity frees up.", confidence=0.8):
    return SimpleNamespace(
        options=options if options is not None else [_option(), _option(title="Add capacity")],
        narrative=narrative, confidence=confidence,
    )


class FakeConfig(AgentConfigGateway):
    def __init__(self, cfg):
        self._cfg = cfg

    def get(self, agent_key):
        return self._cfg


class FakeDecisionDao(DecisionDao):
    def __init__(self):
        self.inserted: list[DecisionRecord] = []

    def insert_decision(self, record):
        self.inserted.append(record)

    def update_selection(self, decision_id, option_id, status):  # pragma: no cover
        raise NotImplementedError

    def update_approval(self, decision_id, status, approved_at):  # pragma: no cover
        raise NotImplementedError

    def list_decisions(self, scope, q, limit, offset):  # pragma: no cover
        raise NotImplementedError

    def get_decision(self, decision_id):  # pragma: no cover
        raise NotImplementedError


class _FailingModel:
    def with_structured_output(self, model):
        class _R:
            def invoke(self, messages):
                raise RuntimeError("model exploded")
        return _R()


def _service(captured=None, cfg=(True, "claude-sonnet-5", "langgraph"),
             collections=COLLECTIONS, dao=None, model=None, decision=None):
    captured = captured if captured is not None else {}

    def builder(model_name):
        captured["model"] = model_name
        return model if model is not None else FakeChatModel([], decision or _decision())

    mongo = FakeMongo(collections)
    return DefaultDecisionService(
        mongo=mongo, evidence_dao=MongoEvidenceDao(mongo),
        agent_config_gateway=FakeConfig(cfg), settings=Settings(),
        chat_model_builder=builder, decisions_dao=dao,
    )


# --- options generation ----------------------------------------------------

def test_decide_leads_with_options_and_drafts() -> None:
    resp = _service().decide(DecisionRequest(project_key="APACHE"))
    assert resp.project_key == "APACHE" and resp.question is None
    assert resp.status == "DRAFTED" and resp.selected_option_id is None
    assert resp.approved_at is None
    assert [o.option_id for o in resp.options] == ["opt-1", "opt-2"]
    assert resp.options[0].title and resp.options[0].actions
    assert resp.narrative and 0.0 <= resp.confidence <= 1.0
    assert resp.run_id and resp.created_at is not None


def test_suggested_owners_derived_from_top_contributors() -> None:
    # Options came back with empty owners -> fall back to the top history authors.
    resp = _service().decide(DecisionRequest(project_key="APACHE"))
    assert resp.options[0].suggested_owners == ["alice", "bob"]


def test_model_supplied_owners_are_kept() -> None:
    dec = _decision(options=[_option(owners=["carol"])])
    resp = _service(decision=dec).decide(DecisionRequest(project_key="APACHE"))
    assert resp.options[0].suggested_owners == ["carol"]


def test_at_most_three_options() -> None:
    dec = _decision(options=[_option(title=f"o{i}") for i in range(5)])
    resp = _service(decision=dec).decide(DecisionRequest(project_key="APACHE"))
    assert len(resp.options) == 3


def test_model_resolved_from_agent_config() -> None:
    captured = {}
    _service(captured, cfg=(True, "claude-sonnet-5", "langgraph")).decide(
        DecisionRequest(project_key="APACHE"))
    assert captured["model"] == "claude-sonnet-5"


def test_model_falls_back_to_default() -> None:
    captured = {}
    _service(captured, cfg=None).decide(DecisionRequest(project_key="APACHE"))
    assert captured["model"] == Settings().default_agent_model


def test_missing_project_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service().decide(DecisionRequest(project_key="GHOST"))


def test_empty_options_fall_back_deterministically() -> None:
    resp = _service(decision=_decision(options=[])).decide(DecisionRequest(project_key="APACHE"))
    assert len(resp.options) == 1
    assert resp.options[0].option_id == "opt-1"
    assert resp.options[0].actions  # deterministic fallback still carries actions


def test_confidence_clamped_when_trajectory_short() -> None:
    single = {
        "projects": COLLECTIONS["projects"],
        "project_metrics": [COLLECTIONS["project_metrics"][0]],
        "issue_histories": COLLECTIONS["issue_histories"],
    }
    resp = _service(collections=single, decision=_decision(confidence=0.95)).decide(
        DecisionRequest(project_key="APACHE"))
    assert resp.confidence <= 0.35


# --- persistence -----------------------------------------------------------

def test_persists_drafted_row() -> None:
    dao = FakeDecisionDao()
    resp = _service(dao=dao).decide(
        DecisionRequest(project_key="APACHE", requested_by="alice"))
    assert len(dao.inserted) == 1
    row = dao.inserted[0]
    assert row.status == "DRAFTED" and row.decision_id == resp.decision_id
    assert row.requested_by == "alice"
    assert len(row.options) == 2


def test_agent_error_persists_failed_and_reraises() -> None:
    dao = FakeDecisionDao()
    with pytest.raises(RuntimeError):
        _service(dao=dao, model=_FailingModel()).decide(
            DecisionRequest(project_key="APACHE", requested_by="bob"))
    assert dao.inserted and dao.inserted[0].status == "FAILED"
    assert dao.inserted[0].confidence is None and dao.inserted[0].options == []


def test_no_dao_degrades_gracefully() -> None:
    resp = _service(dao=None).decide(DecisionRequest(project_key="APACHE"))
    assert resp.status == "DRAFTED"


# --- select / approve transitions ------------------------------------------

def _drafted_service():
    dao = PostgresDecisionDao(fake_decision_db())
    service = _service(dao=dao)
    resp = service.decide(DecisionRequest(project_key="APACHE", requested_by="alice"))
    return service, resp


def test_select_option_sets_selected_state() -> None:
    service, resp = _drafted_service()
    out = service.select_option(resp.decision_id, SelectOptionRequest(option_id="opt-2"))
    assert out.status == "SELECTED" and out.selected_option_id == "opt-2"
    assert out.decision_id == resp.decision_id


def test_select_unknown_option_raises_validation() -> None:
    service, resp = _drafted_service()
    with pytest.raises(ValidationError):
        service.select_option(resp.decision_id, SelectOptionRequest(option_id="opt-99"))


def test_select_missing_decision_raises_not_found() -> None:
    service, _ = _drafted_service()
    with pytest.raises(NotFoundError):
        service.select_option("missing", SelectOptionRequest(option_id="opt-1"))


def test_approve_sets_approved_state_and_timestamp() -> None:
    service, resp = _drafted_service()
    service.select_option(resp.decision_id, SelectOptionRequest(option_id="opt-1"))
    out = service.approve_decision(resp.decision_id)
    assert out.status == "APPROVED" and out.approved_at is not None
    assert out.selected_option_id == "opt-1"  # selection preserved through approval


def test_approve_missing_decision_raises_not_found() -> None:
    service, _ = _drafted_service()
    with pytest.raises(NotFoundError):
        service.approve_decision("missing")


# --- list / get ------------------------------------------------------------

def test_list_and_get_delegate_to_dao() -> None:
    service, resp = _drafted_service()
    page = service.list_decisions(scope=None, q=None, limit=10, offset=0)
    assert page.total == 1 and page.items[0].option_count == 2
    assert service.get_decision(resp.decision_id).decision_id == resp.decision_id


def test_get_missing_decision_raises_not_found() -> None:
    service, _ = _drafted_service()
    with pytest.raises(NotFoundError):
        service.get_decision("missing")


def test_list_without_dao_returns_empty_page() -> None:
    page = _service(dao=None).list_decisions(scope=None, q=None, limit=10, offset=0)
    assert page.total == 0 and page.items == []
