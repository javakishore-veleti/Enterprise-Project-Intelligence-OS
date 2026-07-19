"""resource-risk specialist agent (framework-agnostic port + adapters)."""
from resource_risk.contract import AGENT_KEY, ResourceRiskAgent
from resource_risk.registry import build_agent

__all__ = ["AGENT_KEY", "ResourceRiskAgent", "build_agent"]
