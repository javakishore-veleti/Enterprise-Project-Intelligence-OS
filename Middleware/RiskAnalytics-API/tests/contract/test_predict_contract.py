"""Contract tests for the Predict endpoints (fake facades, no service/LLM/DB).

Exercises routing, request validation, serialization (page shapes, uuid->str),
query-param passthrough, and error mapping only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from risk_analytics_api.api.dependencies import (
    provide_get_early_warnings_facade,
    provide_get_forecast_facade,
    provide_get_scenario_facade,
    provide_list_forecasts_facade,
    provide_list_scenarios_facade,
    provide_run_forecast_facade,
    provide_run_scenario_facade,
)
from risk_analytics_api.api.main import create_app
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.dtos.responses import (
    EarlyWarning,
    EarlyWarningsResponse,
    ForecastDriver,
    ForecastResponse,
    ForecastsPageResponse,
    ForecastSummary,
    ScenarioCascade,
    ScenarioResponse,
    ScenariosPageResponse,
    ScenarioSummary,
)

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _forecast() -> ForecastResponse:
    return ForecastResponse(
        forecast_id="fc-1", project_key="APACHE", question=None,
        on_time_probability=0.62, probability_low=0.5, probability_high=0.74,
        projected_slip_days_low=8, projected_slip_days_high=30, outlook="at_risk",
        drivers=[ForecastDriver(factor="reopen_churn", direction="up", detail="rising")],
        bull_case="lands", bear_case="slips", would_change_mind="velocity recovers",
        narrative="tight", confidence=0.66, status="COMPLETED", run_id="run-1",
        created_at=_NOW,
    )


def _scenario() -> ScenarioResponse:
    return ScenarioResponse(
        scenario_id="sc-1", project_key="APACHE", scenario="move 2 engineers to Payments",
        base_on_time_probability=0.7, projected_on_time_probability=0.58,
        probability_delta=-0.12, base_slip_days=10, projected_slip_days=25,
        portfolio_risk_delta=0.27,
        cascades=[ScenarioCascade(project_key="BILLING", effect="delivery slip risk",
                                  reason="deps", magnitude="high")],
        narrative="trade-off", confidence=0.6, status="COMPLETED", run_id="run-1",
        created_at=_NOW,
    )


class _FakeRunForecast:
    def execute(self, request):
        if request.project_key == "GHOST":
            raise NotFoundError("project 'GHOST' not found")
        return _forecast()


class _FakeListForecasts:
    def __init__(self):
        self.calls = []

    def execute(self, scope, q, limit, offset, projects=None):
        self.calls.append((scope, q, limit, offset, projects))
        return ForecastsPageResponse(
            total=1, returned=1, offset=offset, limit=limit,
            items=[ForecastSummary(forecast_id="fc-1", project_key="APACHE",
                                   on_time_probability=0.62, outlook="at_risk",
                                   projected_slip_days_low=8, projected_slip_days_high=30,
                                   confidence=0.66, status="COMPLETED", created_at=_NOW)])


class _FakeGetForecast:
    def execute(self, forecast_id):
        if forecast_id == "missing":
            raise NotFoundError(f"forecast '{forecast_id}' not found")
        return _forecast()


class _FakeRunScenario:
    def execute(self, request):
        return _scenario()


class _FakeListScenarios:
    def __init__(self):
        self.calls = []

    def execute(self, scope, q, limit, offset, projects=None):
        self.calls.append((scope, q, limit, offset, projects))
        return ScenariosPageResponse(
            total=1, returned=1, offset=offset, limit=limit,
            items=[ScenarioSummary(scenario_id="sc-1", project_key="APACHE",
                                   scenario="move 2 engineers", projected_on_time_probability=0.58,
                                   probability_delta=-0.12, confidence=0.6,
                                   status="COMPLETED", created_at=_NOW)])


class _FakeGetScenario:
    def execute(self, scenario_id):
        if scenario_id == "missing":
            raise NotFoundError(f"scenario '{scenario_id}' not found")
        return _scenario()


class _FakeEarlyWarnings:
    def __init__(self):
        self.calls = []

    def execute(self, scope, limit):
        self.calls.append((scope, limit))
        return EarlyWarningsResponse(items=[EarlyWarning(
            project_key="APACHE", metric="reopen_rate", from_value=0.1, to_value=0.5,
            window="2026-02-01 to 2026-03-01", direction="up", severity="high",
            cause="Reopen churn jumped.", confidence=0.8, detected_at=_NOW)])


def _client(list_fc=None, list_sc=None, ew=None):
    app = create_app()
    o = app.dependency_overrides
    o[provide_run_forecast_facade] = lambda: _FakeRunForecast()
    o[provide_list_forecasts_facade] = lambda: list_fc or _FakeListForecasts()
    o[provide_get_forecast_facade] = lambda: _FakeGetForecast()
    o[provide_run_scenario_facade] = lambda: _FakeRunScenario()
    o[provide_list_scenarios_facade] = lambda: list_sc or _FakeListScenarios()
    o[provide_get_scenario_facade] = lambda: _FakeGetScenario()
    o[provide_get_early_warnings_facade] = lambda: ew or _FakeEarlyWarnings()
    return TestClient(app)


# --- Forecast --------------------------------------------------------------

def test_run_forecast_returns_conclusion() -> None:
    resp = _client().post("/api/v1/analysis/forecast", json={"project_key": "APACHE"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["forecast_id"] == "fc-1" and body["question"] is None
    assert body["outlook"] == "at_risk"
    assert body["drivers"][0]["direction"] == "up"
    assert body["projected_slip_days_low"] == 8


def test_run_forecast_requires_project_key() -> None:
    assert _client().post("/api/v1/analysis/forecast", json={}).status_code == 422


def test_run_forecast_missing_project_maps_404() -> None:
    resp = _client().post("/api/v1/analysis/forecast", json={"project_key": "GHOST"})
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_list_forecasts_page_shape() -> None:
    resp = _client().get("/api/v1/analysis/forecasts?limit=20&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"total", "returned", "offset", "limit", "items"}
    item = body["items"][0]
    assert set(item) == {"forecast_id", "project_key", "on_time_probability", "outlook",
                         "projected_slip_days_low", "projected_slip_days_high",
                         "confidence", "status", "created_at",
                         "subject_type", "subject_value"}


def test_list_forecasts_passes_scope_and_query() -> None:
    facade = _FakeListForecasts()
    _client(list_fc=facade).get("/api/v1/analysis/forecasts?scope=alice&q=churn&limit=5&offset=2")
    assert facade.calls == [("alice", "churn", 5, 2, None)]


def test_list_forecasts_passes_parsed_projects() -> None:
    facade = _FakeListForecasts()
    _client(list_fc=facade).get("/api/v1/analysis/forecasts?projects=APACHE,BILLING")
    assert facade.calls == [(None, None, 20, 0, ["APACHE", "BILLING"])]


def test_list_scenarios_passes_parsed_projects() -> None:
    facade = _FakeListScenarios()
    _client(list_sc=facade).get("/api/v1/analysis/scenarios?projects=APACHE")
    assert facade.calls == [(None, None, 20, 0, ["APACHE"])]


def test_list_forecasts_limit_over_100_rejected() -> None:
    assert _client().get("/api/v1/analysis/forecasts?limit=500").status_code == 422


def test_get_forecast_full_and_404() -> None:
    assert _client().get("/api/v1/analysis/forecasts/fc-9").status_code == 200
    missing = _client().get("/api/v1/analysis/forecasts/missing")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


# --- Scenario --------------------------------------------------------------

def test_run_scenario_returns_result() -> None:
    resp = _client().post("/api/v1/analysis/scenarios",
                          json={"project_key": "APACHE", "scenario": "move 2 engineers"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["scenario_id"] == "sc-1"
    assert body["probability_delta"] == -0.12
    assert body["cascades"][0]["project_key"] == "BILLING"


def test_run_scenario_requires_scenario_text() -> None:
    resp = _client().post("/api/v1/analysis/scenarios", json={"project_key": "APACHE"})
    assert resp.status_code == 422


def test_list_scenarios_page_shape() -> None:
    resp = _client().get("/api/v1/analysis/scenarios")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert set(item) == {"scenario_id", "project_key", "scenario",
                         "projected_on_time_probability", "probability_delta",
                         "confidence", "status", "created_at"}


def test_get_scenario_404() -> None:
    resp = _client().get("/api/v1/analysis/scenarios/missing")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


# --- Early-warning ---------------------------------------------------------

def test_early_warnings_shape_and_passthrough() -> None:
    ew = _FakeEarlyWarnings()
    resp = _client(ew=ew).get("/api/v1/analysis/early-warnings?scope=APACHE,BILLING&limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"items"}
    w = body["items"][0]
    assert set(w) == {"project_key", "metric", "from_value", "to_value", "window",
                      "direction", "severity", "cause", "confidence", "detected_at"}
    assert ew.calls == [("APACHE,BILLING", 5)]
