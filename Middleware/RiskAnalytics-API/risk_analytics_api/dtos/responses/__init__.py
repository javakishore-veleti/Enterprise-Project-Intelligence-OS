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
    #: Review-pipeline annotations (priority_rank, correlation_group, critic_verdict, ...).
    meta: dict = {}


class ReportResponse(TypedModel):
    """A generated narrative report over a run's findings."""

    report_id: str
    kind: str  # mitigation | project | executive
    title: str
    summary: str
    sections: list[dict]
    source_agent: str
    generated_at: datetime


class AnalysisRunResponse(TypedModel):
    """A multi-agent analysis run, its findings, and any review reports."""

    run_id: str
    project_key: str
    status: AnalysisStatus
    agent_keys: list[str]
    started_at: datetime
    finished_at: datetime | None
    findings: list[RiskFindingResponse]
    reports: list[ReportResponse] = []
    #: Number of projects analyzed (portfolio runs only; None for single-project).
    project_count: int | None = None


class AnalysisRunSummary(TypedModel):
    """Compact view of a past analysis run (for the history list)."""

    run_id: str
    project_key: str
    status: AnalysisStatus
    agent_keys: list[str]
    started_at: datetime
    finished_at: datetime | None
    finding_count: int
    report_count: int


class AnalysisRunListResponse(TypedModel):
    project_key: str
    runs: list[AnalysisRunSummary]


class DashboardFindingSummary(TypedModel):
    """Compact cross-project view of a recent risk finding (dashboard activity)."""

    finding_id: str
    run_id: str
    project_key: str
    agent_key: str
    risk_category: str
    severity: str
    score: float
    #: Truncated to ~240 chars for the activity feed.
    explanation: str


class DashboardTotals(TypedModel):
    """Cross-project counts for the dashboard header."""

    total_runs: int
    total_findings: int
    projects_analyzed: int


class DashboardActivityResponse(TypedModel):
    """Recent cross-project activity for the dashboard (runs + findings + totals)."""

    recent_runs: list[AnalysisRunSummary]
    recent_findings: list[DashboardFindingSummary]
    totals: DashboardTotals


class AttentionFindingRow(TypedModel):
    """Raw in-scope finding row read by the attention DAO (pre-scoring).

    A cross-layer DAO->service object: the DAO returns these ordered newest-first
    (capped window); the service scores + sorts + paginates them into AttentionItem.
    """

    finding_id: str
    run_id: str
    project_key: str
    agent_key: str
    risk_category: str
    severity: str
    score: float
    probability: float
    #: NULL-able so the service can apply the missing-confidence default.
    confidence: float | None = None
    explanation: str
    recommended_actions: list[str] = []
    analysis_timestamp: datetime


class AttentionItem(TypedModel):
    """A ranked attention item: a high-priority finding scored for a manager's feed."""

    finding_id: str
    run_id: str
    project_key: str
    agent_key: str
    risk_category: str
    severity: str
    score: float
    probability: float
    confidence: float
    #: Deterministic ranking score in [0, 100].
    attention_score: float
    #: Trimmed to ~240 chars for the feed.
    explanation: str
    recommended_actions: list[str] = []
    analysis_timestamp: datetime


class AttentionResponse(TypedModel):
    """A ranked, scoped, time-aware feed of the highest-priority findings."""

    #: Echo of the requested as-of date (YYYY-MM-DD), or None for "current".
    as_of: str | None
    #: Distinct projects in scope, or -1 when unscoped (all projects).
    scope_projects: int
    #: Total in-scope findings matching scope + as_of (for "view more").
    total: int
    returned: int
    items: list[AttentionItem]


class HealthResponse(TypedModel):
    status: str
    service: str
    dependencies: dict[str, str] = {}
