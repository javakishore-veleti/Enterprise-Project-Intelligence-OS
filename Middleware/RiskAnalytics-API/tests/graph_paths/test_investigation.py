"""Graph-path tests for the Investigation Agent's LangGraph tool-calling loop.

Exercises the real LangGraph graph with a fake chat model (a scripted tool-call
sequence + canned conclusion) over fake-Mongo tools: the loop reasons, calls
tools, records the (action, observation, hypothesis) trace + evidence citations,
and finalizes. Also asserts the loop is bounded and handles an immediate finish.
"""
from __future__ import annotations

from risk_analytics_api.graphs.investigation import InvestigationAgent
from risk_analytics_api.graphs.investigation.tools import build_investigation_tools
from tests.support.llm import FakeChatModel, conclusion, tool_call_msg
from tests.support.mongo import FakeMongo

COLLECTIONS = {
    "projects": [{"project_key": "APACHE", "name": "Apache"}],
    "project_metrics": [{"project_key": "APACHE", "computed_at": "2026-02-01",
                         "blocker_count": 9, "reopen_rate": 0.4}],
    "issue_histories": [
        {"issue_key": "A-1", "project_key": "APACHE", "field": "status",
         "to_value": "Reopened", "changed_at": "2026-01-05", "author": "alice"},
        {"issue_key": "A-2", "project_key": "APACHE", "field": "status",
         "to_value": "Open", "changed_at": "2026-01-07", "author": "bob"},
        {"issue_key": "A-3", "project_key": "APACHE", "field": "status",
         "to_value": "Reopen", "changed_at": "2026-01-08", "author": "alice"},
    ],
}


def _tools():
    return build_investigation_tools(FakeMongo(COLLECTIONS).db(), "APACHE")


def test_agent_calls_tools_records_trace_and_concludes() -> None:
    script = [
        tool_call_msg("Orienting on the metrics", [("metrics_snapshot", {}, "c1")]),
        tool_call_msg("Reopen churn hypothesis", [("reopened_issues", {"limit": 5}, "c2")]),
    ]
    concl = conclusion(
        hypotheses=["reopen churn", "blocker pile-up"],
        root_cause="High reopen rate concentrated in Auth",
        causal_chain=["rework churn", "velocity drop", "schedule slip"],
        confidence=0.72,
        recommended_action="Assign a single owner to Auth reopens",
    )
    agent = InvestigationAgent(FakeChatModel(script, concl), _tools())

    result = agent.run("APACHE", "why is APACHE slipping?")

    # Conclusion mapped from the structured output.
    assert result.root_cause == "High reopen rate concentrated in Auth"
    assert result.confidence == 0.72
    assert result.hypotheses == ["reopen churn", "blocker pile-up"]
    assert result.causal_chain[-1] == "schedule slip"

    # Two tool rounds -> two trace steps, each with action/observation/hypothesis.
    assert len(result.steps) == 2
    assert result.steps[0]["action"].startswith("metrics_snapshot(")
    assert result.steps[0]["hypothesis"] == "Orienting on the metrics"
    assert result.steps[1]["action"] == "reopened_issues(limit=5)"
    assert "count" in result.steps[1]["observation"]  # bounded evidence, from the tool

    # Evidence citations are grounded in the tool results.
    kinds = [e["kind"] for e in result.evidence]
    assert kinds == ["metrics_snapshot", "reopened_issues"]
    reopened = next(e for e in result.evidence if e["kind"] == "reopened_issues")
    assert reopened["count"] == 3  # the real count the tool returned over fake Mongo


def test_loop_is_bounded_by_max_iterations() -> None:
    # Model always wants another tool; the loop must stop at max_iterations.
    script = [tool_call_msg("again", [("reopened_issues", {}, f"c{i}")]) for i in range(6)]
    agent = InvestigationAgent(FakeChatModel(script, conclusion(root_cause="x")),
                               _tools(), max_iterations=2)

    result = agent.run("APACHE")

    assert len(result.steps) == 2  # bounded to max_iterations tool rounds
    assert result.root_cause == "x"  # still finalized


def test_agent_can_finalize_without_calling_tools() -> None:
    script = [tool_call_msg("I already know enough", [])]  # no tool calls
    agent = InvestigationAgent(
        FakeChatModel(script, conclusion(root_cause="obvious", confidence=0.4)), _tools())

    result = agent.run("APACHE")

    assert result.steps == []
    assert result.evidence == []
    assert result.root_cause == "obvious"
