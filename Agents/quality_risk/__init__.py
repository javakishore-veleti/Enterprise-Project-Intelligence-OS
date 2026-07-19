"""Quality-risk specialist agent (framework-agnostic port + adapters)."""
from quality_risk.contract import AGENT_KEY, QualityRiskAgent
from quality_risk.registry import build_agent

__all__ = ["AGENT_KEY", "QualityRiskAgent", "build_agent"]
