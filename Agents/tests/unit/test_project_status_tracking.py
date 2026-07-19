"""Hermetic tests for the project-status-tracking agent package (no LLM calls)."""
from __future__ import annotations

import pytest

from agent_core import EvidenceMetrics, EvidencePackage, RiskCategory
from project_status_tracking.contract import AGENT_KEY, ProjectStatusTrackingAgent
from project_status_tracking.registry import SUPPORTED_FRAMEWORKS, build_agent


def test_contract_identity() -> None:
    assert AGENT_KEY == "project_status_tracking"
    assert ProjectStatusTrackingAgent.category is RiskCategory.DELIVERY


def test_registry_supports_expected_frameworks() -> None:
    assert "langgraph" in SUPPORTED_FRAMEWORKS
    assert {"crewai", "openai_agents", "strands", "google_adk", "ms_agent_framework"} <= set(
        SUPPORTED_FRAMEWORKS
    )


def test_unknown_framework_raises() -> None:
    with pytest.raises(ValueError):
        build_agent("no-such-framework", "claude-opus-4-8")


def test_stub_framework_analyze_not_implemented() -> None:
    agent = build_agent("strands", "claude-opus-4-8")
    evidence = EvidencePackage(project_key="X", project_name="X", metrics=EvidenceMetrics())
    with pytest.raises(NotImplementedError):
        agent.analyze(evidence)
