"""Wiring test for the openai_agents adapter (no LLM call).

Skipped unless the optional `frameworks-openai` extra is installed. Verifies the
registry builds the real adapter (not a stub) for framework 'openai_agents' and
that constructing it needs no network.
"""
from __future__ import annotations

import pytest

pytest.importorskip("agents")  # openai-agents

from schedule_risk.adapters.openai_agents_adapter import OpenAIAgentsScheduleRiskAgent
from schedule_risk.contract import ScheduleRiskAgent
from schedule_risk.registry import IMPLEMENTED_FRAMEWORKS, build_agent


def test_openai_agents_is_marked_implemented() -> None:
    assert "openai_agents" in IMPLEMENTED_FRAMEWORKS


def test_registry_builds_real_openai_agents_adapter() -> None:
    agent = build_agent("openai_agents", "claude-haiku-4-5-20251001")
    assert isinstance(agent, OpenAIAgentsScheduleRiskAgent)
    assert isinstance(agent, ScheduleRiskAgent)
    assert agent.agent_key == "schedule_risk"
