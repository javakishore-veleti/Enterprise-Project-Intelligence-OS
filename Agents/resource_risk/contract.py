"""The resource-risk agent port."""
from __future__ import annotations

from agent_core import RiskAgent, RiskCategory

AGENT_KEY = "resource_risk"


class ResourceRiskAgent(RiskAgent):
    """Assesses resource/capacity risk (workload versus throughput, overload)."""

    agent_key = AGENT_KEY
    category = RiskCategory.RESOURCE
