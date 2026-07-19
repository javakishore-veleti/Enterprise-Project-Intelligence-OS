"""The dependency-risk agent port."""
from __future__ import annotations

from agent_core import RiskAgent, RiskCategory

AGENT_KEY = "dependency_risk"


class DependencyRiskAgent(RiskAgent):
    """Assesses dependency risk (coupling depth, cross-issue blocking chains)."""

    agent_key = AGENT_KEY
    category = RiskCategory.DEPENDENCY
