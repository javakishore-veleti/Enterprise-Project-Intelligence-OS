"""Contract test for the attention feed endpoint with a fake facade.

No DB, no Mongo, no LLM — the facade is faked so this exercises routing,
query-param validation, serialization, and the JSON shape only.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from risk_analytics_api.api.dependencies import provide_get_attention_feed_facade
from risk_analytics_api.api.main import create_app
from risk_analytics_api.dtos.responses import AttentionItem, AttentionResponse

_NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _response() -> AttentionResponse:
    return AttentionResponse(
        as_of=None,
        scope_projects=-1,
        total=2,
        returned=2,
        items=[
            AttentionItem(
                finding_id="f2", run_id="run-2", project_key="SPARK",
                agent_key="schedule_risk", risk_category="schedule", severity="CRITICAL",
                score=88.0, probability=0.9, confidence=0.8, attention_score=95.5,
                explanation="urgent", recommended_actions=["escalate"], analysis_timestamp=_NOW),
            AttentionItem(
                finding_id="f1", run_id="run-1", project_key="APACHE",
                agent_key="quality_risk", risk_category="quality", severity="MEDIUM",
                score=40.0, probability=0.5, confidence=0.6, attention_score=30.0,
                explanation="watch", recommended_actions=[], analysis_timestamp=_NOW),
        ],
    )


class _FakeFacade:
    def __init__(self):
        self.calls: list[tuple] = []

    def execute(self, top, as_of, projects, offset):
        self.calls.append((top, as_of, projects, offset))
        return _response()


def _client(facade) -> TestClient:
    app = create_app()
    app.dependency_overrides[provide_get_attention_feed_facade] = lambda: facade
    return TestClient(app)


def test_attention_shape() -> None:
    resp = _client(_FakeFacade()).get("/api/v1/analysis/attention")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"as_of", "scope_projects", "total", "returned", "items"}
    assert body["scope_projects"] == -1
    assert body["total"] == 2 and body["returned"] == 2
    assert [i["finding_id"] for i in body["items"]] == ["f2", "f1"]
    item = body["items"][0]
    assert set(item) == {
        "finding_id", "run_id", "project_key", "agent_key", "risk_category",
        "severity", "score", "probability", "confidence", "attention_score",
        "explanation", "recommended_actions", "analysis_timestamp"}
    assert item["attention_score"] == 95.5
    assert item["recommended_actions"] == ["escalate"]


def test_default_top_is_10_and_offset_0() -> None:
    facade = _FakeFacade()
    _client(facade).get("/api/v1/analysis/attention")
    top, as_of, projects, offset = facade.calls[0]
    assert top == 10 and offset == 0 and as_of is None and projects is None


def test_as_of_and_projects_params_accepted() -> None:
    facade = _FakeFacade()
    resp = _client(facade).get(
        "/api/v1/analysis/attention?top=5&offset=2&as_of=2026-07-20&projects=APACHE,SPARK")
    assert resp.status_code == 200
    top, as_of, projects, offset = facade.calls[0]
    assert top == 5 and offset == 2
    assert as_of == date(2026, 7, 20)
    assert projects == ["APACHE", "SPARK"]


def test_rejects_out_of_range_top() -> None:
    assert _client(_FakeFacade()).get("/api/v1/analysis/attention?top=0").status_code == 422
    assert _client(_FakeFacade()).get("/api/v1/analysis/attention?top=101").status_code == 422


def test_rejects_negative_offset() -> None:
    assert _client(_FakeFacade()).get("/api/v1/analysis/attention?offset=-1").status_code == 422


def test_rejects_bad_as_of() -> None:
    resp = _client(_FakeFacade()).get("/api/v1/analysis/attention?as_of=not-a-date")
    assert resp.status_code == 422
