"""The backlog-health agent port."""
from __future__ import annotations

from agent_core import RiskAgent, RiskCategory

AGENT_KEY = "backlog_health"


class BacklogHealthAgent(RiskAgent):
    """Assesses backlog health (growth, aging open work, rework accumulation)."""

    agent_key = AGENT_KEY
    category = RiskCategory.BACKLOG
