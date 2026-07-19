"""The quality-risk agent port."""
from __future__ import annotations

from agent_core import RiskAgent, RiskCategory

AGENT_KEY = "quality_risk"


class QualityRiskAgent(RiskAgent):
    """Assesses quality/defect risk (rework, reopens, unresolved defects)."""

    agent_key = AGENT_KEY
    category = RiskCategory.QUALITY
