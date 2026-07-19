"""Hermetic tests for the schedule-risk agent package (no LLM calls)."""
from __future__ import annotations

import pytest

from agent_core import EvidenceMetrics, EvidencePackage, RiskCategory, Severity
from schedule_risk.contract import AGENT_KEY, ScheduleRiskAgent
from schedule_risk.registry import SUPPORTED_FRAMEWORKS, build_agent
from schedule_risk.tools import risk_score, severity_from_score


def test_risk_score_is_deterministic_product() -> None:
    assert risk_score(0.5, 0.5) == 25.0
    assert risk_score(1.0, 1.0) == 100.0
    assert risk_score(2.0, 2.0) == 100.0  # clamped
    assert risk_score(-1.0, 0.5) == 0.0  # clamped


def test_severity_bands() -> None:
    assert severity_from_score(10) is Severity.LOW
    assert severity_from_score(25) is Severity.MEDIUM
    assert severity_from_score(50) is Severity.HIGH
    assert severity_from_score(80) is Severity.CRITICAL


def test_contract_identity() -> None:
    assert AGENT_KEY == "schedule_risk"
    assert ScheduleRiskAgent.category is RiskCategory.SCHEDULE


def test_registry_supports_expected_frameworks() -> None:
    assert "langgraph" in SUPPORTED_FRAMEWORKS
    assert {"crewai", "openai_agents", "strands", "google_adk", "ms_agent_framework"} <= set(
        SUPPORTED_FRAMEWORKS
    )


def test_unknown_framework_raises() -> None:
    with pytest.raises(ValueError):
        build_agent("no-such-framework", "claude-opus-4-8")


def test_stub_framework_builds_but_analyze_not_implemented() -> None:
    agent = build_agent("crewai", "claude-opus-4-8")
    evidence = EvidencePackage(
        project_key="X", project_name="X", metrics=EvidenceMetrics()
    )
    with pytest.raises(NotImplementedError):
        agent.analyze(evidence)
