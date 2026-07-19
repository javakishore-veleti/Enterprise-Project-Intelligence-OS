"""Stub adapters for the non-default frameworks (delivery-forecasting agent)."""
from __future__ import annotations

from agent_core import EvidencePackage, RiskFinding
from delivery_forecasting.contract import DeliveryForecastingAgent


class _NotYetImplementedAgent(DeliveryForecastingAgent):
    framework_name = "unknown"

    def __init__(self, model: str) -> None:
        self._model = model

    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        raise NotImplementedError(
            f"The '{self.framework_name}' adapter for delivery_forecasting is not implemented yet."
        )


class CrewAIDeliveryForecastingAgent(_NotYetImplementedAgent):
    framework_name = "crewai"


class OpenAIAgentsDeliveryForecastingAgent(_NotYetImplementedAgent):
    framework_name = "openai_agents"


class StrandsDeliveryForecastingAgent(_NotYetImplementedAgent):
    framework_name = "strands"


class GoogleADKDeliveryForecastingAgent(_NotYetImplementedAgent):
    framework_name = "google_adk"


class MSAgentFrameworkDeliveryForecastingAgent(_NotYetImplementedAgent):
    framework_name = "ms_agent_framework"
