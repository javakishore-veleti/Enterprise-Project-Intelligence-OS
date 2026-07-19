"""dependency-risk specialist agent (framework-agnostic port + adapters)."""
from dependency_risk.contract import AGENT_KEY, DependencyRiskAgent
from dependency_risk.registry import build_agent

__all__ = ["AGENT_KEY", "DependencyRiskAgent", "build_agent"]
