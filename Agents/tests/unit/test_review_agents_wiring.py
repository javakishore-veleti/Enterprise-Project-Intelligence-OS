"""Wiring tests for all 8 review-pipeline agents (import + identity, no LLM)."""
from __future__ import annotations

import importlib

DETERMINISTIC = ["risk_scoring", "risk_deduplication", "risk_correlation"]
LLM = ["evidence_validation", "critic", "mitigation_planning", "project_reporting", "executive_reporting"]


def test_all_review_agents_import_and_expose_build_and_key() -> None:
    for name in DETERMINISTIC + LLM:
        mod = importlib.import_module(name)
        assert mod.AGENT_KEY == name
        assert callable(mod.build)


def test_deterministic_processors_construct_without_llm() -> None:
    # These need no model/key — build() returns a ready processor.
    for name in DETERMINISTIC:
        mod = importlib.import_module(name)
        proc = mod.build()
        assert proc.agent_key == name
        assert hasattr(proc, "process")
