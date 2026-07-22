"""Graph-path tests for the bounded forecast + scenario narration graphs.

Exercises the real single-node LangGraph with a fake chat model (canned
structured narration) and asserts the deterministic facts are rendered into the
prompt block the model is asked to interpret.
"""
from __future__ import annotations

from types import SimpleNamespace

from agent_core import EvidenceMetrics, EvidencePackage
from risk_analytics_api.graphs.forecast import ForecastNarrator, format_facts
from risk_analytics_api.graphs.scenario import ScenarioNarrator
from risk_analytics_api.graphs.scenario import format_facts as scenario_facts
from risk_analytics_api.services.forecast.forecasting import compute_forecast
from tests.support.llm import FakeChatModel


def _evidence() -> EvidencePackage:
    return EvidencePackage(
        project_key="APACHE", project_name="Apache",
        metrics=EvidenceMetrics(reopen_rate=0.3, blocker_count=5, open_issue_count=40,
                                issue_count=100),
        observations=["Reopen rate is 30%."],
    )


def _forecast_narration():
    return SimpleNamespace(narrative="tight", bull_case="lands", bear_case="slips",
                           would_change_mind="velocity", confidence=0.75)


def test_forecast_narrator_returns_structured_narration() -> None:
    facts = compute_forecast(
        [{"reopen_rate": 0.3, "blocker_count": 5, "resolution_velocity": 8,
          "computed_at": "2026-03-01"},
         {"reopen_rate": 0.1, "blocker_count": 2, "resolution_velocity": 10,
          "computed_at": "2026-02-01"}],
        {"issue_count": 100, "open_issue_count": 40},
    )
    narrator = ForecastNarrator(FakeChatModel([], _forecast_narration()))
    out = narrator.run(facts, _evidence())
    assert out.narrative == "tight"
    assert out.bull_case == "lands" and out.confidence == 0.75


def test_format_facts_renders_probability_and_drivers() -> None:
    facts = compute_forecast(
        [{"reopen_rate": 0.5, "blocker_count": 12, "resolution_velocity_trend": -6,
          "computed_at": "2026-03-01"},
         {"reopen_rate": 0.1, "blocker_count": 2, "resolution_velocity_trend": 0,
          "computed_at": "2026-02-01"}],
        {"issue_count": 100, "open_issue_count": 60},
    )
    block = format_facts(facts, _evidence())
    assert "On-time probability" in block
    assert "Projected slip" in block
    assert "Outlook" in block
    assert "blocker_burn_rate" in block  # a driver surfaced into the prompt


def test_scenario_narrator_returns_structured_narration() -> None:
    cascades = [{"project_key": "BILLING", "effect": "delivery slip risk",
                 "reason": "deps", "magnitude": "high"}]
    block = scenario_facts(0.7, 0.58, 10, 25, 0.27, cascades)
    assert "BILLING" in block and "Portfolio risk delta" in block

    narrator = ScenarioNarrator(FakeChatModel([], SimpleNamespace(narrative="trade-off", confidence=0.6)))
    out = narrator.run("move 2 engineers to Payments", block)
    assert out.narrative == "trade-off" and out.confidence == 0.6
