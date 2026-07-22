"""Graph-path tests for the bounded Decide options graph.

Exercises the real single-node LangGraph with a fake chat model (canned
structured options) and asserts the deterministic facts + candidate owners are
rendered into the prompt block, and that an empty model result falls back to a
deterministic option so the decision is never lost.
"""
from __future__ import annotations

from types import SimpleNamespace

from agent_core import EvidenceMetrics, EvidencePackage
from risk_analytics_api.graphs.decision import DecisionOptionsAgent, format_facts
from risk_analytics_api.services.forecast.forecasting import compute_forecast
from tests.support.llm import FakeChatModel


def _evidence() -> EvidencePackage:
    return EvidencePackage(
        project_key="APACHE", project_name="Apache",
        metrics=EvidenceMetrics(reopen_rate=0.3, blocker_count=5, open_issue_count=40,
                                issue_count=100),
        observations=["Reopen rate is 30%.", "5 open blocker issue(s)."],
    )


def _facts():
    return compute_forecast(
        [{"reopen_rate": 0.3, "blocker_count": 5, "resolution_velocity": 8,
          "computed_at": "2026-03-01"},
         {"reopen_rate": 0.1, "blocker_count": 2, "resolution_velocity": 10,
          "computed_at": "2026-02-01"}],
        {"issue_count": 100, "open_issue_count": 40},
    )


def _option(title="Reprioritize", **kw):
    base = dict(title=title, summary="s", actions=["a1"], suggested_owners=[],
                predicted_outcome="p", tradeoffs="t", recovery_estimate="2w", confidence=0.7)
    base.update(kw)
    return SimpleNamespace(**base)


def test_format_facts_renders_forecast_blockers_and_owners() -> None:
    block = format_facts(_facts(), _evidence(), ["alice", "bob"], context="ship by Q3")
    assert "On-time probability" in block
    assert "Open blockers: 5" in block
    assert "Candidate owners" in block and "alice" in block
    assert "ship by Q3" in block  # requester context surfaced


def test_agent_returns_structured_options() -> None:
    canned = SimpleNamespace(
        narrative="prefer opt-1", confidence=0.8,
        options=[_option(), _option(title="Add capacity")])
    agent = DecisionOptionsAgent(FakeChatModel([], canned))
    out = agent.run(_facts(), _evidence(), ["alice", "bob"])
    assert out.narrative == "prefer opt-1" and out.confidence == 0.8
    assert [o.title for o in out.options] == ["Reprioritize", "Add capacity"]


def test_empty_options_fall_back_deterministically() -> None:
    canned = SimpleNamespace(narrative="", confidence=0.5, options=[])
    agent = DecisionOptionsAgent(FakeChatModel([], canned))
    out = agent.run(_facts(), _evidence(), ["alice"])
    assert len(out.options) == 1 and out.options[0].actions
