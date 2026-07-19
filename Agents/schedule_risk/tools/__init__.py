"""Deterministic helpers shared by schedule-risk adapters (no LLM).

Kept framework-free so every adapter scores findings identically; only the
orchestration/reasoning differs per framework.
"""
from __future__ import annotations

from agent_core import Severity


def severity_from_score(score: float) -> Severity:
    """Map a 0-100 risk score to a severity band."""
    if score >= 75:
        return Severity.CRITICAL
    if score >= 50:
        return Severity.HIGH
    if score >= 25:
        return Severity.MEDIUM
    return Severity.LOW


def risk_score(probability: float, impact: float) -> float:
    """Deterministic overall score from probability and impact (0-100)."""
    return round(max(0.0, min(1.0, probability)) * max(0.0, min(1.0, impact)) * 100.0, 1)
