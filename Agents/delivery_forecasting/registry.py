"""Framework toggle: build a delivery-forecasting agent for the configured framework."""
from __future__ import annotations

from delivery_forecasting.contract import DeliveryForecastingAgent

_LANGGRAPH = "langgraph"
_STUBS = {
    "crewai": "CrewAIDeliveryForecastingAgent",
    "openai_agents": "OpenAIAgentsDeliveryForecastingAgent",
    "strands": "StrandsDeliveryForecastingAgent",
    "google_adk": "GoogleADKDeliveryForecastingAgent",
    "ms_agent_framework": "MSAgentFrameworkDeliveryForecastingAgent",
}

SUPPORTED_FRAMEWORKS = (_LANGGRAPH, *_STUBS.keys())


def build_agent(framework: str, model: str) -> DeliveryForecastingAgent:
    framework = (framework or _LANGGRAPH).lower()
    if framework == _LANGGRAPH:
        from delivery_forecasting.adapters.langgraph_adapter import LangGraphDeliveryForecastingAgent

        return LangGraphDeliveryForecastingAgent(model=model)
    if framework in _STUBS:
        from delivery_forecasting.adapters import other_frameworks

        return getattr(other_frameworks, _STUBS[framework])(model=model)
    raise ValueError(
        f"unknown framework '{framework}'. Supported: {', '.join(SUPPORTED_FRAMEWORKS)}"
    )
