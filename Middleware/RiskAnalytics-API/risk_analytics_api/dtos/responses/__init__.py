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


class InvestigationStep(TypedModel):
    """One step in the investigator's visible reasoning trace."""

    #: What the agent did (the tool it called + how).
    action: str
    #: The bounded evidence the tool returned (compact summary).
    observation: str
    #: The hypothesis the agent was testing at this step.
    hypothesis: str


class EvidenceCitation(TypedModel):
    """A cited piece of evidence pulled from the evidence store during the run."""

    #: The evidence kind (the tool/source, e.g. "reopened_issues").
    kind: str
    #: Human-readable detail of what was observed.
    detail: str
    #: The count behind the citation, when the observation is a count (else None).
    count: int | None = None


class InvestigationResponse(TypedModel):
    """The autonomous Investigation Agent's conclusion + evidence + confidence."""

    investigation_id: str
    project_key: str
    question: str | None = None
    template_key: str | None = None
    status: str = "COMPLETED"
    hypotheses: list[str] = []
    steps: list[InvestigationStep] = []
    root_cause: str
    causal_chain: list[str] = []
    confidence: float
    evidence: list[EvidenceCitation] = []
    recommended_action: str
    run_id: str
    generated_at: datetime


class InvestigationSummary(TypedModel):
    """Compact view of a past investigation (for the history list)."""

    investigation_id: str
    project_key: str
    question: str | None = None
    template_key: str | None = None
    status: str
    root_cause: str | None = None
    confidence: float | None = None
    #: ISO-8601 serialized by FastAPI/pydantic.
    created_at: datetime


class InvestigationsPageResponse(TypedModel):
    """A capped, newest-first page of investigation history (max 100 rows)."""

    total: int
    returned: int
    offset: int
    limit: int
    items: list[InvestigationSummary] = []


class InvestigationTemplateResponse(TypedModel):
    """A pre-configured investigation template that biases the agent's focus."""

    template_key: str
    name: str
    description: str
    #: The investigative angles / tool-emphasis this template steers toward.
    steps: list[str] = []
    editable: bool = True


class InvestigationRecord(TypedModel):
    """Cross-layer persistence object: a full investigation row for the DAO to insert."""

    investigation_id: str
    project_key: str
    requested_by: str | None = None
    question: str | None = None
    template_key: str | None = None
    status: str
    root_cause: str | None = None
    confidence: float | None = None
    recommended_action: str | None = None
    hypotheses: list[str] = []
    causal_chain: list[str] = []
    steps: list[InvestigationStep] = []
    evidence: list[EvidenceCitation] = []
    run_id: str | None = None
    created_at: datetime


# --- Predict: Delivery Forecast -------------------------------------------


class ForecastDriver(TypedModel):
    """A factor moving the forecast, with the direction of its recent movement."""

    #: The factor name (e.g. "resolution_velocity", "blocker_burn_rate").
    factor: str
    #: Which way the factor moved recently.
    direction: str  # up | down | flat
    #: Human-readable detail of the movement and why it matters.
    detail: str


class ForecastResponse(TypedModel):
    """A delivery forecast: deterministic probability/interval/slip + drivers,
    plus the grounded LLM narrative (bull/bear/would-change-mind)."""

    forecast_id: str
    project_key: str
    #: Forecast granularity: project | release | component | tag.
    subject_type: str = "project"
    #: The release/component/tag scoped to (null for a whole-project forecast).
    subject_value: str | None = None
    #: Always null on a forecast (the field exists to mirror investigations).
    question: str | None = None
    on_time_probability: float
    probability_low: float
    probability_high: float
    projected_slip_days_low: int
    projected_slip_days_high: int
    outlook: str  # on_track | at_risk | off_track
    drivers: list[ForecastDriver] = []
    bull_case: str = ""
    bear_case: str = ""
    would_change_mind: str = ""
    narrative: str = ""
    confidence: float
    status: str = "COMPLETED"
    run_id: str
    created_at: datetime


class ForecastSummary(TypedModel):
    """Compact view of a past forecast (for the history list)."""

    forecast_id: str
    project_key: str
    subject_type: str = "project"
    subject_value: str | None = None
    on_time_probability: float | None = None
    outlook: str | None = None
    projected_slip_days_low: int | None = None
    projected_slip_days_high: int | None = None
    confidence: float | None = None
    status: str
    created_at: datetime


class ForecastsPageResponse(TypedModel):
    """A capped, newest-first page of forecast history (max 100 rows)."""

    total: int
    returned: int
    offset: int
    limit: int
    items: list[ForecastSummary] = []


class ForecastRecord(TypedModel):
    """Cross-layer persistence object: a full forecast row for the DAO to insert."""

    forecast_id: str
    project_key: str
    subject_type: str = "project"
    subject_value: str | None = None
    requested_by: str | None = None
    status: str
    on_time_probability: float | None = None
    probability_low: float | None = None
    probability_high: float | None = None
    projected_slip_days_low: int | None = None
    projected_slip_days_high: int | None = None
    outlook: str | None = None
    drivers: list[ForecastDriver] = []
    bull_case: str | None = None
    bear_case: str | None = None
    would_change_mind: str | None = None
    narrative: str | None = None
    confidence: float | None = None
    run_id: str | None = None
    created_at: datetime


# --- Predict: Digital-Twin Scenario Simulator -----------------------------


class ScenarioCascade(TypedModel):
    """One project the scenario propagates to (via dependency links or shared staff)."""

    project_key: str
    #: Short label of the effect on the target (e.g. "delivery slip risk").
    effect: str
    #: Why this project is affected (the dependency / shared-contributor link).
    reason: str
    magnitude: str  # high | medium | low


class ScenarioResponse(TypedModel):
    """A digital-twin scenario result: re-forecast + portfolio cascade + narrative."""

    scenario_id: str
    project_key: str
    scenario: str
    base_on_time_probability: float
    projected_on_time_probability: float
    probability_delta: float
    base_slip_days: int
    projected_slip_days: int
    portfolio_risk_delta: float
    cascades: list[ScenarioCascade] = []
    narrative: str = ""
    confidence: float
    status: str = "COMPLETED"
    run_id: str
    created_at: datetime


class ScenarioSummary(TypedModel):
    """Compact view of a past scenario (for the history list)."""

    scenario_id: str
    project_key: str
    scenario: str
    projected_on_time_probability: float | None = None
    probability_delta: float | None = None
    confidence: float | None = None
    status: str
    created_at: datetime


class ScenariosPageResponse(TypedModel):
    """A capped, newest-first page of scenario history (max 100 rows)."""

    total: int
    returned: int
    offset: int
    limit: int
    items: list[ScenarioSummary] = []


class ScenarioRecord(TypedModel):
    """Cross-layer persistence object: a full scenario row for the DAO to insert."""

    scenario_id: str
    project_key: str
    requested_by: str | None = None
    scenario: str
    status: str
    base_on_time_probability: float | None = None
    projected_on_time_probability: float | None = None
    probability_delta: float | None = None
    base_slip_days: int | None = None
    projected_slip_days: int | None = None
    portfolio_risk_delta: float | None = None
    cascades: list[ScenarioCascade] = []
    narrative: str | None = None
    confidence: float | None = None
    run_id: str | None = None
    created_at: datetime


# --- Predict: Early-Warning (computed on read, not persisted) --------------


class EarlyWarning(TypedModel):
    """A detected adverse inflection in a project's metric trajectory."""

    project_key: str
    #: The metric that moved adversely (e.g. "reopen_rate").
    metric: str
    from_value: float
    to_value: float
    #: Human-readable window the move happened over.
    window: str
    direction: str  # up | down
    severity: str  # high | medium | low
    #: Plain-language cause of the inflection.
    cause: str
    confidence: float
    detected_at: datetime


class EarlyWarningsResponse(TypedModel):
    """Ranked adverse inflections across the in-scope projects (most severe first)."""

    items: list[EarlyWarning] = []


# --- Decide: Options-first decision support --------------------------------


class DecisionOption(TypedModel):
    """One prescriptive decision option — Decide leads with these.

    The chosen option's ``actions`` + ``suggested_owners`` ARE the plan (no
    separate plan-generation step)."""

    #: Stable id assigned by the service (e.g. "opt-1"), used to select the option.
    option_id: str
    title: str
    summary: str = ""
    #: Prioritized concrete steps (most important first).
    actions: list[str] = []
    #: Owners derived from the project's top contributors (history authorship).
    suggested_owners: list[str] = []
    predicted_outcome: str = ""
    tradeoffs: str = ""
    recovery_estimate: str = ""
    confidence: float = 0.5


class DecisionResponse(TypedModel):
    """A prescriptive decision: the generated options + the comparison narrative,
    plus which option was selected/approved. ``question`` always null (mirrors the
    forecast DTO shape)."""

    decision_id: str
    project_key: str
    #: Always null on a decision (the field exists to mirror investigations/forecasts).
    question: str | None = None
    options: list[DecisionOption] = []
    selected_option_id: str | None = None
    status: str  # DRAFTED | SELECTED | APPROVED | FAILED
    narrative: str = ""
    confidence: float
    run_id: str
    created_at: datetime
    approved_at: datetime | None = None


class DecisionSummary(TypedModel):
    """Compact view of a past decision (for the history list)."""

    decision_id: str
    project_key: str
    status: str
    option_count: int
    selected_option_id: str | None = None
    confidence: float | None = None
    created_at: datetime


class DecisionsPageResponse(TypedModel):
    """A capped, newest-first page of decision history (max 100 rows)."""

    total: int
    returned: int
    offset: int
    limit: int
    items: list[DecisionSummary] = []


class DecisionRecord(TypedModel):
    """Cross-layer persistence object: a full decision row for the DAO to insert."""

    decision_id: str
    project_key: str
    requested_by: str | None = None
    status: str
    options: list[DecisionOption] = []
    selected_option_id: str | None = None
    narrative: str | None = None
    confidence: float | None = None
    run_id: str | None = None
    created_at: datetime
    approved_at: datetime | None = None


class HealthResponse(TypedModel):
    status: str
    service: str
    dependencies: dict[str, str] = {}
