"""Wiring tests for the scenario service (fake Mongo, fake LLM, no infra).

Verifies the seam: project check -> base forecast -> effect applied -> cascade
propagation -> narrator (fake LLM) -> DTO assembly + persistence.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.dtos.requests import ScenarioRequest
from risk_analytics_api.dtos.responses import ScenarioRecord
from risk_analytics_api.interfaces.daos import AgentConfigGateway, ScenarioDao
from risk_analytics_api.services.scenario import DefaultScenarioService
from tests.support.llm import FakeChatModel
from tests.support.mongo import FakeMongo

COLLECTIONS = {
    "projects": [{"project_key": "APACHE", "name": "Apache",
                  "issue_count": 100, "open_issue_count": 40}],
    "project_metrics": [
        {"project_key": "APACHE", "computed_at": "2026-03-01", "reopen_rate": 0.3,
         "blocker_count": 5, "resolution_velocity": 8},
        {"project_key": "APACHE", "computed_at": "2026-02-01", "reopen_rate": 0.2,
         "blocker_count": 3, "resolution_velocity": 10},
    ],
    "issue_links": [
        {"project_key": "APACHE", "source_issue_key": "APACHE-1",
         "target_issue_key": "BILLING-9", "link_type": "blocks"},
        {"project_key": "APACHE", "source_issue_key": "APACHE-2",
         "target_issue_key": "BILLING-4", "link_type": "depends on"},
    ],
    "issue_histories": [
        {"project_key": "APACHE", "author": "alice"},
        {"project_key": "BILLING", "author": "alice"},
    ],
}


def _narration(**kw):
    base = dict(narrative="Helps Payments, costs Apache.", confidence=0.7)
    base.update(kw)
    return SimpleNamespace(**base)


class FakeConfig(AgentConfigGateway):
    def __init__(self, cfg):
        self._cfg = cfg

    def get(self, agent_key):
        return self._cfg


class FakeScenarioDao(ScenarioDao):
    def __init__(self):
        self.inserted: list[ScenarioRecord] = []

    def insert_scenario(self, record):
        self.inserted.append(record)

    def list_scenarios(self, scope, q, limit, offset, projects=None):  # pragma: no cover
        raise NotImplementedError

    def get_scenario(self, scenario_id):  # pragma: no cover
        raise NotImplementedError


class _FailingModel:
    def with_structured_output(self, model):
        class _R:
            def invoke(self, messages):
                raise RuntimeError("model exploded")
        return _R()


def _service(captured, cfg=(True, "claude-sonnet-5", "langgraph"),
             collections=COLLECTIONS, dao=None, model=None):
    def builder(model_name):
        captured["model"] = model_name
        return model if model is not None else FakeChatModel([], _narration())

    return DefaultScenarioService(
        mongo=FakeMongo(collections), agent_config_gateway=FakeConfig(cfg),
        settings=Settings(), chat_model_builder=builder, scenarios_dao=dao,
    )


def test_scenario_returns_typed_response_with_cascade() -> None:
    resp = _service({}).simulate(
        ScenarioRequest(project_key="APACHE", scenario="move 2 engineers to Payments"))
    assert resp.project_key == "APACHE"
    assert resp.scenario == "move 2 engineers to Payments"
    # Moving people away worsens the source: projected < base.
    assert resp.projected_on_time_probability < resp.base_on_time_probability
    assert resp.probability_delta < 0
    # BILLING is coupled (deps + shared contributor) -> a cascade target.
    assert "BILLING" in {c.project_key for c in resp.cascades}
    assert resp.narrative == "Helps Payments, costs Apache."
    assert resp.run_id and resp.created_at is not None


def test_add_capacity_improves_odds() -> None:
    resp = _service({}).simulate(
        ScenarioRequest(project_key="APACHE", scenario="add 3 engineers to the team"))
    assert resp.projected_on_time_probability > resp.base_on_time_probability
    assert resp.probability_delta > 0


def test_missing_project_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service({}).simulate(ScenarioRequest(project_key="GHOST", scenario="add staff"))


def test_persists_completed_row() -> None:
    dao = FakeScenarioDao()
    resp = _service({}, dao=dao).simulate(
        ScenarioRequest(project_key="APACHE", scenario="descope reporting",
                        requested_by="alice"))
    assert len(dao.inserted) == 1
    row = dao.inserted[0]
    assert row.status == "COMPLETED" and row.scenario_id == resp.scenario_id
    assert row.requested_by == "alice"


def test_agent_error_persists_failed_and_reraises() -> None:
    dao = FakeScenarioDao()
    with pytest.raises(RuntimeError):
        _service({}, dao=dao, model=_FailingModel()).simulate(
            ScenarioRequest(project_key="APACHE", scenario="add staff", requested_by="bob"))
    assert dao.inserted and dao.inserted[0].status == "FAILED"
    assert dao.inserted[0].confidence is None


def test_no_dao_degrades_gracefully() -> None:
    resp = _service({}, dao=None).simulate(
        ScenarioRequest(project_key="APACHE", scenario="add staff"))
    assert resp.status == "COMPLETED"


def test_list_and_get_delegate_to_dao() -> None:
    from risk_analytics_api.daos.scenarios import PostgresScenarioDao
    from tests.support.pg_predict import fake_scenario_db

    dao = PostgresScenarioDao(fake_scenario_db())
    service = _service({}, dao=dao)
    resp = service.simulate(
        ScenarioRequest(project_key="APACHE", scenario="add staff", requested_by="alice"))
    page = service.list_scenarios(scope=None, q=None, limit=10, offset=0)
    assert page.total == 1
    assert service.get_scenario(resp.scenario_id).scenario_id == resp.scenario_id


def test_get_missing_scenario_raises_not_found() -> None:
    from risk_analytics_api.daos.scenarios import PostgresScenarioDao
    from tests.support.pg_predict import fake_scenario_db

    service = _service({}, dao=PostgresScenarioDao(fake_scenario_db()))
    with pytest.raises(NotFoundError):
        service.get_scenario("missing")
