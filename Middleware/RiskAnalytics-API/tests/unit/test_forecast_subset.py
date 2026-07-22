"""Forecast scoping: filtered-subset input math + the subject-scoped service path.

Covers the pure ``compute_subset_signals`` (deterministic inputs over a filtered
issue set) and the service branch that filters the evidence issues to a
release/component/tag, feeds them through ``compute_forecast``, echoes + persists
the subject, and widens/​lowers-confidence on a tiny subset. Fake Mongo/pg/LLM —
no infra, no model call.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.daos.evidence import MongoEvidenceDao
from risk_analytics_api.dtos.requests import ForecastRequest
from risk_analytics_api.dtos.responses import ForecastRecord
from risk_analytics_api.interfaces.daos import AgentConfigGateway, ForecastDao
from risk_analytics_api.services.forecast import DefaultForecastService
from risk_analytics_api.services.forecast.subset import compute_subset_signals
from tests.support.llm import FakeChatModel
from tests.support.mongo import FakeMongo

REF = datetime(2025, 6, 1, tzinfo=timezone.utc)


def _days(n: int) -> datetime:
    return REF - timedelta(days=n)


# --- pure subset-signal math ---------------------------------------------- #
def test_compute_subset_signals_counts_ratios_and_windows() -> None:
    issues = [
        {"issue_key": "A-1", "status": "Open", "priority": "Blocker",
         "created_at": _days(5), "resolved_at": None},
        {"issue_key": "A-2", "status": "Open", "priority": "Critical",
         "created_at": _days(50), "resolved_at": None},
        {"issue_key": "A-3", "status": "Closed", "priority": "Major",
         "created_at": _days(40), "resolved_at": _days(10)},   # resolved in window
        {"issue_key": "A-4", "status": "Done", "priority": "Minor",
         "created_at": _days(200), "resolved_at": _days(100)},  # resolved outside windows
    ]
    histories = [
        {"issue_key": "A-3", "to_value": "Reopened", "author": "alice"},
        {"issue_key": "A-3", "to_value": "Closed", "author": "alice"},
        {"issue_key": "A-1", "to_value": "In Progress", "author": "bob"},
    ]
    snap, project = compute_subset_signals(issues, histories)

    assert project == {"issue_count": 4, "open_issue_count": 2}
    assert snap["blocker_count"] == 1                       # A-1 open Blocker
    assert snap["critical_defect_ratio"] == 1.0            # A-1 + A-2 open critical / 2 open
    assert snap["resolution_velocity"] == 1.0             # A-3 resolved in window
    assert snap["resolution_velocity_trend"] == 1.0       # 1 - 0 prior
    assert snap["reopen_rate"] == 0.5                     # 1 reopened / 2 resolved
    assert snap["contributor_concentration"] == round(2 / 3, 3)  # alice 2 of 3
    assert snap["dependency_depth"] == 0
    assert snap["issue_aging_days"] > 0


def test_compute_subset_signals_empty_subset_is_neutral() -> None:
    snap, project = compute_subset_signals([], [])
    assert project == {"issue_count": 0, "open_issue_count": 0}
    assert snap["reopen_rate"] == 0.0 and snap["blocker_count"] == 0
    assert snap["resolution_velocity"] == 0.0 and snap["backlog_growth"] == 0.0


# --- subject-scoped service path ------------------------------------------ #
def _narration(**kw):
    base = dict(narrative="It will be tight.", bull_case="lands if velocity recovers",
                bear_case="slips if blockers grow", would_change_mind="a velocity rebound",
                confidence=0.9)
    base.update(kw)
    return SimpleNamespace(**base)


class _FakeConfig(AgentConfigGateway):
    def get(self, agent_key):
        return (True, "claude-sonnet-5", "langgraph")


class _FakeForecastDao(ForecastDao):
    def __init__(self):
        self.inserted: list[ForecastRecord] = []

    def insert_forecast(self, record):
        self.inserted.append(record)

    def list_forecasts(self, scope, q, limit, offset):  # pragma: no cover
        raise NotImplementedError

    def get_forecast(self, forecast_id):  # pragma: no cover
        raise NotImplementedError


def _issue(key, release, *, status="Open", priority="Major", created=10, resolved=None):
    return {"issue_key": key, "project_key": "APACHE", "status": status,
            "priority": priority, "created_at": _days(created),
            "resolved_at": _days(resolved) if resolved is not None else None,
            "fix_versions": [release], "components": ["core"], "labels": ["perf"]}


def _collections(release_2_count=12, release_1_count=3):
    issues = []
    for i in range(release_2_count):
        issues.append(_issue(
            f"AP-2-{i}", "2.0",
            status="Open" if i % 2 else "Closed",
            priority="Blocker" if i % 4 == 0 else "Major",
            created=5 + i, resolved=None if i % 2 else 8 + i))
    for i in range(release_1_count):
        issues.append(_issue(f"AP-1-{i}", "1.0", status="Open",
                             priority="Blocker", created=3 + i))
    histories = [
        {"issue_key": "AP-2-0", "project_key": "APACHE", "field": "status",
         "to_value": "Reopened", "author": "alice"},
        {"issue_key": "AP-2-1", "project_key": "APACHE", "field": "status",
         "to_value": "In Progress", "author": "bob"},
    ]
    return {
        "projects": [{"project_key": "APACHE", "name": "Apache",
                      "issue_count": 100, "open_issue_count": 40}],
        "project_metrics": [],
        "issues": issues,
        "issue_histories": histories,
    }


def _service(collections, dao=None, narration=None):
    mongo = FakeMongo(collections)
    return DefaultForecastService(
        mongo=mongo, evidence_dao=MongoEvidenceDao(mongo),
        agent_config_gateway=_FakeConfig(), settings=Settings(),
        chat_model_builder=lambda m: FakeChatModel([], narration or _narration()),
        forecasts_dao=dao,
    )


def test_release_subject_scopes_and_persists_subject() -> None:
    dao = _FakeForecastDao()
    resp = _service(_collections(), dao=dao).forecast(
        ForecastRequest(project_key="APACHE", subject_type="release",
                        subject_value="2.0", requested_by="alice"))
    assert resp.subject_type == "release" and resp.subject_value == "2.0"
    assert 0.0 <= resp.probability_low <= resp.on_time_probability <= resp.probability_high <= 1.0
    assert resp.outlook in {"on_track", "at_risk", "off_track"}
    # subject persisted on the row
    assert dao.inserted and dao.inserted[0].subject_type == "release"
    assert dao.inserted[0].subject_value == "2.0"


def test_tiny_subset_widens_interval_and_lowers_confidence() -> None:
    # release 1.0 has 3 issues -> tiny subset
    resp = _service(_collections()).forecast(
        ForecastRequest(project_key="APACHE", subject_type="release", subject_value="1.0"))
    assert resp.confidence <= 0.2
    assert (resp.probability_high - resp.probability_low) >= 0.3


def test_unknown_subject_value_yields_empty_neutral_forecast() -> None:
    resp = _service(_collections()).forecast(
        ForecastRequest(project_key="APACHE", subject_type="tag", subject_value="does-not-exist"))
    # no issues matched -> neutral single-point forecast, still typed + subject echoed
    assert resp.subject_type == "tag" and resp.subject_value == "does-not-exist"
    assert resp.status == "COMPLETED"
    assert resp.confidence <= 0.2


def test_project_default_path_ignores_subject_fields() -> None:
    resp = _service(_collections()).forecast(ForecastRequest(project_key="APACHE"))
    assert resp.subject_type == "project" and resp.subject_value is None


def test_subject_round_trips_through_pg_dao() -> None:
    from risk_analytics_api.daos.forecasts import PostgresForecastDao
    from tests.support.pg_predict import fake_forecast_db

    dao = PostgresForecastDao(fake_forecast_db())
    service = _service(_collections(), dao=dao)
    resp = service.forecast(ForecastRequest(
        project_key="APACHE", subject_type="component", subject_value="core",
        requested_by="x"))
    full = service.get_forecast(resp.forecast_id)
    assert full.subject_type == "component" and full.subject_value == "core"
    page = service.list_forecasts(scope=None, q=None, limit=10, offset=0)
    assert page.items[0].subject_type == "component"
    assert page.items[0].subject_value == "core"


def test_subject_value_required_when_not_project() -> None:
    import pytest

    with pytest.raises(Exception):
        ForecastRequest(project_key="APACHE", subject_type="release")
