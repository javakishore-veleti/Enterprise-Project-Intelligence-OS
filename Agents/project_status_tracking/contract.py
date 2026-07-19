"""The project-status-tracking agent port."""
from __future__ import annotations

from agent_core import RiskAgent, RiskCategory

AGENT_KEY = "project_status_tracking"


class ProjectStatusTrackingAgent(RiskAgent):
    """Assesses overall delivery/status health (trajectory, throughput, stalls)."""

    agent_key = AGENT_KEY
    category = RiskCategory.DELIVERY
