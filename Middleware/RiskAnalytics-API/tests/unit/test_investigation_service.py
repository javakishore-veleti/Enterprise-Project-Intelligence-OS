"""Wiring tests for the investigation service (fake Mongo, fake LLM, no infra).

Verifies the full seam: project existence check -> model resolution from config
-> tools built over Mongo -> agent run (fake LLM) -> DTO assembly, with no real
model call.
"""
from __future__ import annotations

import pytest

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.dtos.requests import InvestigateRequest
from risk_analytics_api.dtos.responses import (
    EvidenceCitation,
    InvestigationRecord,
    InvestigationStep,
)
from risk_analytics_api.interfaces.daos import AgentConfigGateway, InvestigationDao
from risk_analytics_api.services.investigation import DefaultInvestigationService
from tests.support.llm import FakeChatModel, conclusion, tool_call_msg
from tests.support.mongo import FakeMongo

COLLECTIONS = {
    "projects": [{"project_key": "APACHE", "name": "Apache"}],
    "project_metrics": [{"project_key": "APACHE", "computed_at": "2026-02-01",
                         "blocker_count": 9, "reopen_rate": 0.4}],
    "issue_histories": [
        {"issue_key": "A-1", "project_key": "APACHE", "field": "status",
         "to_value": "Reopened", "changed_at": "2026-01-05", "author": "alice"},
    ],
}


class FakeConfig(AgentConfigGateway):
    def __init__(self, cfg):
        self._cfg = cfg

    def get(self, agent_key):
        return self._cfg


class FakeInvestigationDao(InvestigationDao):
    """Captures the inserted record; not used for list/get here."""

    def __init__(self):
        self.inserted: list[InvestigationRecord] = []

    def insert_investigation(self, record: InvestigationRecord) -> None:
        self.inserted.append(record)

    def list_investigations(self, scope, q, limit, offset):  # pragma: no cover - unused
        raise NotImplementedError

    def get_investigation(self, investigation_id):  # pragma: no cover - unused
        raise NotImplementedError


class _FailingModel:
    """A chat model whose tool-bound runnable raises when invoked."""

    def bind_tools(self, tools):
        class _R:
            def invoke(self, messages):
                raise RuntimeError("model exploded")
        return _R()

    def with_structured_output(self, model):
        class _R:
            def invoke(self, messages):  # pragma: no cover - never reached
                return conclusion()
        return _R()


def _service(captured: dict, cfg=(True, "claude-sonnet-5", "langgraph"),
             collections=COLLECTIONS, dao=None, model=None):
    script = [tool_call_msg("orient", [("metrics_snapshot", {}, "c1")]),
              tool_call_msg("reopens", [("reopened_issues", {"limit": 5}, "c2")])]
    concl = conclusion(hypotheses=["reopen churn"], root_cause="High reopen rate",
                       causal_chain=["churn", "slip"], confidence=0.8,
                       recommended_action="Assign an owner")

    def builder(model_name: str):
        captured["model"] = model_name
        return model if model is not None else FakeChatModel(script, concl)

    return DefaultInvestigationService(
        mongo=FakeMongo(collections),
        agent_config_gateway=FakeConfig(cfg),
        settings=Settings(),
        chat_model_builder=builder,
        investigations_dao=dao,
    )


def test_investigate_returns_typed_response() -> None:
    captured = {}
    service = _service(captured)

    resp = service.investigate(InvestigateRequest(project_key="APACHE", question="why slipping?"))

    assert resp.project_key == "APACHE"
    assert resp.question == "why slipping?"
    assert resp.root_cause == "High reopen rate"
    assert resp.confidence == 0.8
    assert resp.run_id and resp.generated_at is not None
    assert all(isinstance(s, InvestigationStep) for s in resp.steps)
    assert all(isinstance(e, EvidenceCitation) for e in resp.evidence)
    assert [e.kind for e in resp.evidence] == ["metrics_snapshot", "reopened_issues"]


def test_model_resolved_from_agent_config() -> None:
    captured = {}
    _service(captured, cfg=(True, "claude-sonnet-5", "langgraph")).investigate(
        InvestigateRequest(project_key="APACHE"))
    assert captured["model"] == "claude-sonnet-5"  # builder got the configured model


def test_model_falls_back_to_default_when_unconfigured() -> None:
    captured = {}
    _service(captured, cfg=None).investigate(InvestigateRequest(project_key="APACHE"))
    assert captured["model"] == Settings().default_agent_model


def test_missing_project_raises_not_found() -> None:
    captured = {}
    service = _service(captured)
    with pytest.raises(NotFoundError):
        service.investigate(InvestigateRequest(project_key="GHOST"))


def test_persists_completed_row_with_investigation_id() -> None:
    dao = FakeInvestigationDao()
    resp = _service({}, dao=dao).investigate(
        InvestigateRequest(project_key="APACHE", question="why slipping?", requested_by="alice"))

    assert len(dao.inserted) == 1
    row = dao.inserted[0]
    assert row.status == "COMPLETED"
    assert row.investigation_id == resp.investigation_id  # same id on row + response
    assert row.project_key == "APACHE"
    assert row.requested_by == "alice"
    assert row.root_cause == "High reopen rate"
    assert row.run_id == resp.run_id
    assert [e.kind for e in row.evidence] == ["metrics_snapshot", "reopened_issues"]
    assert resp.status == "COMPLETED"


def test_default_template_is_full_and_recorded() -> None:
    dao = FakeInvestigationDao()
    resp = _service({}, dao=dao).investigate(InvestigateRequest(project_key="APACHE"))
    assert resp.template_key == "full"
    assert dao.inserted[0].template_key == "full"


def test_explicit_template_recorded() -> None:
    dao = FakeInvestigationDao()
    resp = _service({}, dao=dao).investigate(
        InvestigateRequest(project_key="APACHE", template_key="quality"))
    assert resp.template_key == "quality"
    assert dao.inserted[0].template_key == "quality"


def test_unknown_template_falls_back_to_full() -> None:
    dao = FakeInvestigationDao()
    resp = _service({}, dao=dao).investigate(
        InvestigateRequest(project_key="APACHE", template_key="bogus"))
    assert resp.template_key == "full"


def test_agent_error_persists_failed_and_reraises() -> None:
    dao = FakeInvestigationDao()
    service = _service({}, dao=dao, model=_FailingModel())
    with pytest.raises(RuntimeError):
        service.investigate(InvestigateRequest(project_key="APACHE", requested_by="bob"))

    assert len(dao.inserted) == 1
    row = dao.inserted[0]
    assert row.status == "FAILED"
    assert row.project_key == "APACHE"
    assert row.requested_by == "bob"
    assert row.confidence is None


def test_no_dao_degrades_gracefully() -> None:
    # No DAO wired -> still returns a result, nothing persisted.
    resp = _service({}, dao=None).investigate(InvestigateRequest(project_key="APACHE"))
    assert resp.root_cause == "High reopen rate"


def test_list_templates_exposes_three_defaults() -> None:
    templates = _service({}).list_templates()
    keys = [t.template_key for t in templates]
    assert keys == ["full", "quality", "delivery"]
    assert all(t.steps and t.editable for t in templates)


def test_list_and_get_delegate_to_dao() -> None:
    from tests.support.pg import FakePostgresDatabase
    from risk_analytics_api.daos.investigations import PostgresInvestigationDao

    pg_dao = PostgresInvestigationDao(FakePostgresDatabase())
    service = _service({}, dao=pg_dao)
    service.investigate(InvestigateRequest(project_key="APACHE", requested_by="alice"))

    page = service.list_investigations(scope=None, q=None, limit=10, offset=0)
    assert page.total == 1 and page.returned == 1
    fetched = service.get_investigation(page.items[0].investigation_id)
    assert fetched.status == "COMPLETED"


def test_get_missing_investigation_raises_not_found() -> None:
    from tests.support.pg import FakePostgresDatabase
    from risk_analytics_api.daos.investigations import PostgresInvestigationDao

    service = _service({}, dao=PostgresInvestigationDao(FakePostgresDatabase()))
    with pytest.raises(NotFoundError):
        service.get_investigation("missing")
