"""Contract tests for the Phase-2 org-scope integration over the RiskAnalytics
read/run path. Real routers wired to recording fake facades + a fake org-access
gateway (no Postgres, no Mongo, no network). Exercises:

- ``X-Org-Subject`` / ``X-Org-Key`` narrow the history-list ``projects`` filter
- org scope AND-composed with the existing ``projects=`` query filter (intersection)
- empty visible set -> empty ``projects`` filter (isolation, not "all")
- no org headers -> behavior 100% unchanged (filter stays None)
- org API unreachable -> graceful degradation to no org scope
- attention + activity narrowed to the visible set
- get-by-id / run 404 when the project is outside a present org scope (no leak)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from risk_analytics_api.api.dependencies import (
    provide_get_analysis_run_facade,
    provide_get_attention_feed_facade,
    provide_get_dashboard_activity_facade,
    provide_get_forecast_facade,
    provide_list_decisions_facade,
    provide_list_forecasts_facade,
    provide_org_gateway,
    provide_run_forecast_facade,
    provide_start_project_analysis_facade,
)
from risk_analytics_api.api.main import create_app
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.responses import (
    AnalysisRunResponse,
    AttentionResponse,
    DashboardActivityResponse,
    DashboardTotals,
    DecisionsPageResponse,
    ForecastDriver,
    ForecastResponse,
    ForecastsPageResponse,
    ForecastSummary,
)
from risk_analytics_api.interfaces.daos import OrgAccessGateway
from tests.unit.test_org_gateway import FakeOrgGateway

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)

# org gateway resolutions (external_key == project_key)
VISIBLE = {"bob": ["CALM"], "carol": ["CALM", "MID"], "empty": []}
EFFECTIVE = {"org-1": ["RISKY", "CALM"]}


def _forecast(project_key: str = "APACHE") -> ForecastResponse:
    return ForecastResponse(
        forecast_id="fc-1", project_key=project_key, question=None,
        on_time_probability=0.62, probability_low=0.5, probability_high=0.74,
        projected_slip_days_low=8, projected_slip_days_high=30, outlook="at_risk",
        drivers=[ForecastDriver(factor="reopen_churn", direction="up", detail="rising")],
        bull_case="lands", bear_case="slips", would_change_mind="velocity recovers",
        narrative="tight", confidence=0.66, status="COMPLETED", run_id="run-1",
        created_at=_NOW,
    )


def _run(project_key: str = "APACHE") -> AnalysisRunResponse:
    return AnalysisRunResponse(
        run_id="run-1", project_key=project_key, status=AnalysisStatus.COMPLETED,
        agent_keys=["schedule_risk"], started_at=_NOW, finished_at=_NOW, findings=[],
    )


# --- recording fakes -------------------------------------------------------- #
class _RecordingList:
    """Records the (scope, q, limit, offset, projects) the router passes."""

    def __init__(self, page_factory):
        self.calls = []
        self._page = page_factory

    def execute(self, scope, q, limit, offset, projects=None):
        self.calls.append((scope, q, limit, offset, projects))
        return self._page(limit, offset)


def _forecasts_page(limit, offset):
    return ForecastsPageResponse(
        total=0, returned=0, offset=offset, limit=limit, items=[])


def _decisions_page(limit, offset):
    return DecisionsPageResponse(
        total=0, returned=0, offset=offset, limit=limit, items=[])


class _RecordingAttention:
    def __init__(self):
        self.calls = []

    def execute(self, top, as_of, projects, offset):
        self.calls.append(projects)
        return AttentionResponse(
            as_of=None, scope_projects=-1, total=0, returned=0, items=[])


class _RecordingActivity:
    def __init__(self):
        self.calls = []

    def execute(self, limit, projects=None):
        self.calls.append(projects)
        return DashboardActivityResponse(
            recent_runs=[], recent_findings=[],
            totals=DashboardTotals(total_runs=0, total_findings=0, projects_analyzed=0))


class _FakeGetForecast:
    def __init__(self, project_key="APACHE"):
        self._pk = project_key

    def execute(self, forecast_id):
        if forecast_id == "missing":
            raise NotFoundError("forecast 'missing' not found")
        return _forecast(self._pk)


class _FakeGetRun:
    def __init__(self, project_key="APACHE"):
        self._pk = project_key

    def execute(self, run_id):
        return _run(self._pk)


class _FakeRunForecast:
    """POST /forecast — records whether the facade was actually reached."""

    def __init__(self):
        self.called = False

    def execute(self, request):
        self.called = True
        return _forecast(request.project_key)


class _FakeStartAnalysis:
    def __init__(self):
        self.called = False

    def execute(self, project_key, request):
        self.called = True
        return _run(project_key)


def _const(value):
    """A zero-arg provider returning ``value``. Must be zero-arg: FastAPI
    introspects the override's signature, so a ``lambda x=value: x`` would expose
    ``x`` as a spurious dependency parameter."""
    return lambda: value


def _client(overrides=None, gateway: OrgAccessGateway | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[provide_org_gateway] = _const(
        gateway or FakeOrgGateway(visible=VISIBLE, effective=EFFECTIVE))
    for provider, impl in (overrides or {}).items():
        app.dependency_overrides[provider] = _const(impl)
    return TestClient(app)


# --- (a) history lists: org scope narrows the projects filter --------------- #
def test_list_forecasts_scoped_by_org_subject() -> None:
    fac = _RecordingList(_forecasts_page)
    _client({provide_list_forecasts_facade: fac}).get(
        "/api/v1/analysis/forecasts", headers={"X-Org-Subject": "bob"})
    assert fac.calls == [(None, None, 20, 0, ["CALM"])]


def test_list_forecasts_scoped_by_org_key_uses_effective() -> None:
    fac = _RecordingList(_forecasts_page)
    _client({provide_list_forecasts_facade: fac}).get(
        "/api/v1/analysis/forecasts", headers={"X-Org-Key": "org-1"})
    assert set(fac.calls[0][4]) == {"RISKY", "CALM"}


def test_list_forecasts_org_scope_intersects_with_projects_param() -> None:
    # ?projects=CALM,RISKY AND bob's org scope [CALM] -> intersection [CALM].
    fac = _RecordingList(_forecasts_page)
    _client({provide_list_forecasts_facade: fac}).get(
        "/api/v1/analysis/forecasts?projects=CALM,RISKY", headers={"X-Org-Subject": "bob"})
    assert fac.calls == [(None, None, 20, 0, ["CALM"])]


def test_list_forecasts_empty_org_scope_yields_empty_filter() -> None:
    fac = _RecordingList(_forecasts_page)
    _client({provide_list_forecasts_facade: fac}).get(
        "/api/v1/analysis/forecasts", headers={"X-Org-Subject": "empty"})
    # empty list (not None) -> DAO applies an authoritative "match nothing".
    assert fac.calls == [(None, None, 20, 0, [])]


def test_list_forecasts_no_org_headers_unchanged() -> None:
    fac = _RecordingList(_forecasts_page)
    _client({provide_list_forecasts_facade: fac}).get("/api/v1/analysis/forecasts")
    assert fac.calls == [(None, None, 20, 0, None)]


def test_list_forecasts_gateway_down_degrades_to_no_scope() -> None:
    fac = _RecordingList(_forecasts_page)
    _client({provide_list_forecasts_facade: fac},
            gateway=FakeOrgGateway(down=True)).get(
        "/api/v1/analysis/forecasts", headers={"X-Org-Subject": "bob"})
    # graceful: no 500, filter stays None (legacy behavior)
    assert fac.calls == [(None, None, 20, 0, None)]


def test_list_decisions_scoped_by_org_subject() -> None:
    # a second history list, proving the pattern is wired for all four.
    fac = _RecordingList(_decisions_page)
    _client({provide_list_decisions_facade: fac}).get(
        "/api/v1/analysis/decisions", headers={"X-Org-Subject": "carol"})
    assert set(fac.calls[0][4]) == {"CALM", "MID"}


# --- (b) attention + activity narrowed to the visible set ------------------- #
def test_attention_scoped_by_org_subject() -> None:
    fac = _RecordingAttention()
    _client({provide_get_attention_feed_facade: fac}).get(
        "/api/v1/analysis/attention", headers={"X-Org-Subject": "carol"})
    assert set(fac.calls[0]) == {"CALM", "MID"}


def test_attention_no_headers_unchanged() -> None:
    fac = _RecordingAttention()
    _client({provide_get_attention_feed_facade: fac}).get("/api/v1/analysis/attention")
    assert fac.calls == [None]


def test_activity_scoped_by_org_key() -> None:
    fac = _RecordingActivity()
    _client({provide_get_dashboard_activity_facade: fac}).get(
        "/api/v1/analysis/activity", headers={"X-Org-Key": "org-1"})
    assert set(fac.calls[0]) == {"RISKY", "CALM"}


def test_activity_empty_org_scope_yields_empty_filter() -> None:
    fac = _RecordingActivity()
    _client({provide_get_dashboard_activity_facade: fac}).get(
        "/api/v1/analysis/activity", headers={"X-Org-Subject": "empty"})
    assert fac.calls == [[]]


def test_activity_no_headers_unchanged() -> None:
    fac = _RecordingActivity()
    _client({provide_get_dashboard_activity_facade: fac}).get("/api/v1/analysis/activity")
    assert fac.calls == [None]


# --- (c) get-by-id honors the org scope (404 outside, no leak) -------------- #
def test_get_forecast_inside_org_scope_ok() -> None:
    resp = _client({provide_get_forecast_facade: _FakeGetForecast("CALM")}).get(
        "/api/v1/analysis/forecasts/fc-1", headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 200 and resp.json()["project_key"] == "CALM"


def test_get_forecast_outside_org_scope_is_404() -> None:
    # bob may only see CALM -> a RISKY forecast is indistinguishable from missing.
    resp = _client({provide_get_forecast_facade: _FakeGetForecast("RISKY")}).get(
        "/api/v1/analysis/forecasts/fc-1", headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_get_forecast_no_org_headers_unchanged() -> None:
    resp = _client({provide_get_forecast_facade: _FakeGetForecast("RISKY")}).get(
        "/api/v1/analysis/forecasts/fc-1")
    assert resp.status_code == 200


def test_get_analysis_run_outside_org_scope_is_404() -> None:
    resp = _client({provide_get_analysis_run_facade: _FakeGetRun("RISKY")}).get(
        "/api/v1/analysis/runs/run-1", headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 404


def test_get_analysis_run_inside_org_scope_ok() -> None:
    resp = _client({provide_get_analysis_run_facade: _FakeGetRun("CALM")}).get(
        "/api/v1/analysis/runs/run-1", headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 200


# --- (d) run endpoints honor the org scope (404 outside; facade not reached)- #
def test_run_forecast_outside_org_scope_is_404_without_running() -> None:
    fac = _FakeRunForecast()
    resp = _client({provide_run_forecast_facade: fac}).post(
        "/api/v1/analysis/forecast", json={"project_key": "RISKY"},
        headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 404
    assert fac.called is False  # guarded before the analysis ran


def test_run_forecast_inside_org_scope_runs() -> None:
    fac = _FakeRunForecast()
    resp = _client({provide_run_forecast_facade: fac}).post(
        "/api/v1/analysis/forecast", json={"project_key": "CALM"},
        headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 201 and fac.called is True


def test_run_forecast_no_org_headers_unchanged() -> None:
    fac = _FakeRunForecast()
    resp = _client({provide_run_forecast_facade: fac}).post(
        "/api/v1/analysis/forecast", json={"project_key": "RISKY"})
    assert resp.status_code == 201 and fac.called is True


def test_start_project_analysis_outside_org_scope_is_404() -> None:
    fac = _FakeStartAnalysis()
    resp = _client({provide_start_project_analysis_facade: fac}).post(
        "/api/v1/analysis/projects/RISKY", json={}, headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 404 and fac.called is False


def test_start_project_analysis_inside_org_scope_runs() -> None:
    fac = _FakeStartAnalysis()
    resp = _client({provide_start_project_analysis_facade: fac}).post(
        "/api/v1/analysis/projects/CALM", json={}, headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 201 and fac.called is True
