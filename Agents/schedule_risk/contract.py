"""The schedule-risk agent port.

Extends the shared ``RiskAgent`` with this agent's identity. Adapters in
``adapters/`` implement it under a specific framework; ``registry.py`` selects
one from configuration.
"""
from __future__ import annotations

from agent_core import RiskAgent, RiskCategory

AGENT_KEY = "schedule_risk"


class ScheduleRiskAgent(RiskAgent):
    """Assesses schedule/timeline delivery risk from project evidence."""

    agent_key = AGENT_KEY
    category = RiskCategory.SCHEDULE
