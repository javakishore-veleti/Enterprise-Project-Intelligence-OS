"""The delivery-forecasting agent port."""
from __future__ import annotations

from agent_core import RiskAgent, RiskCategory

AGENT_KEY = "delivery_forecasting"


class DeliveryForecastingAgent(RiskAgent):
    """Assesses release readiness by forecasting completion against open work and churn."""

    agent_key = AGENT_KEY
    category = RiskCategory.RELEASE_READINESS
