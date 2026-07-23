"""Wiring tests for the forecast service (fake Mongo, fake LLM, no infra).

Verifies the seam: project check -> deterministic facts from the trajectory ->
model resolution -> narrator (fake LLM) -> DTO assembly + persistence, with no
real model call.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.daos.evidence import MongoEvidenceDao
from risk_analytics_api.dtos.requests import ForecastRequest
from risk_analytics_api.dtos.responses import ForecastRecord
from risk_analytics_api.interfaces.daos import AgentConfigGateway, ForecastDao
from risk_analytics_api.services.forecast import DefaultForecastService
from tests.support.llm import FakeChatModel
from tests.support.mongo import FakeMongo

COLLECTIONS = {
    "projects": [{"project_key": "APACHE", "name": "Apache",
                  "issue_count": 100, "open_issue_count": 40}],
    "project_metrics": [
        {"project_key": "APACHE", "computed_at": "2026-03-01", "reopen_rate": 0.4,
         "blocker_count": 8, "resolution_velocity": 6, "resolution_velocity_trend": -4},
        {"project_key": "APACHE", "computed_at": "2026-02-01", "reopen_rate": 0.2,
         "blocker_count": 3, "resolution_velocity": 10, "resolution_velocity_trend": 1},
    ],
}


def _narration(**kw):
    base = dict(narrative="It will be tight.", bull_case="lands if velocity recovers",
                bear_case="slips if blockers grow", would_change_mind="a velocity rebound",
                confidence=0.8)
    base.update(kw)
    return SimpleNamespace(**base)


class FakeConfig(AgentConfigGateway):
    def __init__(self, cfg):
        self._cfg = cfg

    def get(self, agent_key):
        return self._cfg


class FakeForecastDao(ForecastDao):
    def __init__(self):
        self.inserted: list[ForecastRecord] = []

    def insert_forecast(self, record):
        self.inserted.append(record)

    def list_forecasts(self, scope, q, limit, offset, projects=None):  # pragma: no cover
        raise NotImplementedError

    def get_forecast(self, forecast_id):  # pragma: no cover
        raise NotImplementedError


class _FailingModel:
    def with_structured_output(self, model):
        class _R:
            def invoke(self, messages):
                raise RuntimeError("model exploded")
        return _R()


def _service(captured, cfg=(True, "claude-sonnet-5", "langgraph"),
             collections=COLLECTIONS, dao=None, model=None, narration=None):
    def builder(model_name):
        captured["model"] = model_name
        return model if model is not None else FakeChatModel([], narration or _narration())

    mongo = FakeMongo(collections)
    return DefaultForecastService(
        mongo=mongo, evidence_dao=MongoEvidenceDao(mongo),
        agent_config_gateway=FakeConfig(cfg), settings=Settings(),
        chat_model_builder=builder, forecasts_dao=dao,
    )


def test_forecast_returns_typed_response_grounded_in_facts() -> None:
    resp = _service({}).forecast(ForecastRequest(project_key="APACHE"))
    assert resp.project_key == "APACHE" and resp.question is None
    assert 0.0 <= resp.probability_low <= resp.on_time_probability <= resp.probability_high <= 1.0
    assert resp.projected_slip_days_low <= resp.projected_slip_days_high
    assert resp.outlook in {"on_track", "at_risk", "off_track"}
    assert resp.narrative == "It will be tight."
    assert resp.bull_case and resp.bear_case and resp.would_change_mind
    assert resp.drivers  # trajectory moved -> drivers extracted
    assert resp.run_id and resp.created_at is not None


def test_model_resolved_from_agent_config() -> None:
    captured = {}
    _service(captured, cfg=(True, "claude-sonnet-5", "langgraph")).forecast(
        ForecastRequest(project_key="APACHE"))
    assert captured["model"] == "claude-sonnet-5"


def test_model_falls_back_to_default() -> None:
    captured = {}
    _service(captured, cfg=None).forecast(ForecastRequest(project_key="APACHE"))
    assert captured["model"] == Settings().default_agent_model


def test_missing_project_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        _service({}).forecast(ForecastRequest(project_key="GHOST"))


def test_persists_completed_row() -> None:
    dao = FakeForecastDao()
    resp = _service({}, dao=dao).forecast(
        ForecastRequest(project_key="APACHE", requested_by="alice"))
    assert len(dao.inserted) == 1
    row = dao.inserted[0]
    assert row.status == "COMPLETED" and row.forecast_id == resp.forecast_id
    assert row.requested_by == "alice"
    assert row.on_time_probability == resp.on_time_probability


def test_agent_error_persists_failed_and_reraises() -> None:
    dao = FakeForecastDao()
    with pytest.raises(RuntimeError):
        _service({}, dao=dao, model=_FailingModel()).forecast(
            ForecastRequest(project_key="APACHE", requested_by="bob"))
    assert dao.inserted and dao.inserted[0].status == "FAILED"
    assert dao.inserted[0].confidence is None


def test_no_dao_degrades_gracefully() -> None:
    resp = _service({}, dao=None).forecast(ForecastRequest(project_key="APACHE"))
    assert resp.status == "COMPLETED"


def test_confidence_clamped_when_trajectory_short() -> None:
    single = {
        "projects": COLLECTIONS["projects"],
        "project_metrics": [COLLECTIONS["project_metrics"][0]],  # one snapshot only
    }
    resp = _service({}, collections=single, narration=_narration(confidence=0.9)).forecast(
        ForecastRequest(project_key="APACHE"))
    assert resp.confidence <= 0.35


def test_list_and_get_delegate_to_dao() -> None:
    from risk_analytics_api.daos.forecasts import PostgresForecastDao
    from tests.support.pg_predict import fake_forecast_db

    dao = PostgresForecastDao(fake_forecast_db())
    service = _service({}, dao=dao)
    resp = service.forecast(ForecastRequest(project_key="APACHE", requested_by="alice"))
    page = service.list_forecasts(scope=None, q=None, limit=10, offset=0)
    assert page.total == 1
    assert service.get_forecast(resp.forecast_id).forecast_id == resp.forecast_id


def test_get_missing_forecast_raises_not_found() -> None:
    from risk_analytics_api.daos.forecasts import PostgresForecastDao
    from tests.support.pg_predict import fake_forecast_db

    service = _service({}, dao=PostgresForecastDao(fake_forecast_db()))
    with pytest.raises(NotFoundError):
        service.get_forecast("missing")
