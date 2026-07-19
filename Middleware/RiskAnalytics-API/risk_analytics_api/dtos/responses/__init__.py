"""Outbound response DTOs (never expose raw database entities)."""
from __future__ import annotations

from datetime import datetime

from risk_analytics_api.common.models import TypedModel
from risk_analytics_api.dtos.common import AnalysisStatus


class RiskFindingResponse(TypedModel):
    """A persisted risk finding surfaced to clients."""

    finding_id: str
    agent_key: str
    risk_category: str
    probability: float
    impact: float
    severity: str
    score: float
    confidence: float
    explanation: str
    assumptions: list[str]
    recommended_actions: list[str]
    affected: list[str]
    analysis_timestamp: datetime


class AnalysisRunResponse(TypedModel):
    """A multi-agent analysis run and its findings."""

    run_id: str
    project_key: str
    status: AnalysisStatus
    agent_keys: list[str]
    started_at: datetime
    finished_at: datetime | None
    findings: list[RiskFindingResponse]


class HealthResponse(TypedModel):
    status: str
    service: str
    dependencies: dict[str, str] = {}
