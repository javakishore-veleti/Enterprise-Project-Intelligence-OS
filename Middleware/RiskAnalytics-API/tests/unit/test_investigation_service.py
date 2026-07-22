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
from risk_analytics_api.dtos.responses import EvidenceCitation, InvestigationStep
from risk_analytics_api.interfaces.daos import AgentConfigGateway
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


def _service(captured: dict, cfg=(True, "claude-sonnet-5", "langgraph"), collections=COLLECTIONS):
    script = [tool_call_msg("orient", [("metrics_snapshot", {}, "c1")]),
              tool_call_msg("reopens", [("reopened_issues", {"limit": 5}, "c2")])]
    concl = conclusion(hypotheses=["reopen churn"], root_cause="High reopen rate",
                       causal_chain=["churn", "slip"], confidence=0.8,
                       recommended_action="Assign an owner")

    def builder(model: str):
        captured["model"] = model
        return FakeChatModel(script, concl)

    return DefaultInvestigationService(
        mongo=FakeMongo(collections),
        agent_config_gateway=FakeConfig(cfg),
        settings=Settings(),
        chat_model_builder=builder,
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
