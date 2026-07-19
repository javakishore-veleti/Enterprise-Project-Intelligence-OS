"""Hermetic tests for the delivery-forecasting agent package (no LLM calls)."""
from __future__ import annotations

import pytest

from agent_core import EvidenceMetrics, EvidencePackage, RiskCategory
from delivery_forecasting.contract import AGENT_KEY, DeliveryForecastingAgent
from delivery_forecasting.registry import SUPPORTED_FRAMEWORKS, build_agent


def test_contract_identity() -> None:
    assert AGENT_KEY == "delivery_forecasting"
    assert DeliveryForecastingAgent.category is RiskCategory.RELEASE_READINESS


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
