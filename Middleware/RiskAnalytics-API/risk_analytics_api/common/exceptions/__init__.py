"""Domain exception hierarchy shared across layers."""
from __future__ import annotations


class RiskAnalyticsError(Exception):
    code: str = "risk_analytics_error"
    http_status: int = 500


class NotFoundError(RiskAnalyticsError):
    code = "not_found"
    http_status = 404


class ValidationError(RiskAnalyticsError):
    code = "validation_error"
    http_status = 422


class AgentExecutionError(RiskAnalyticsError):
    """An agent failed to produce findings (e.g. the model call failed)."""

    code = "agent_execution_error"
    http_status = 502


class DependencyUnavailableError(RiskAnalyticsError):
    code = "dependency_unavailable"
    http_status = 503
