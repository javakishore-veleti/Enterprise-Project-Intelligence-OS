"""Framework-agnostic agent contracts (the shared *port*).

Every specialist agent consumes an ``EvidencePackage`` and produces
``RiskFinding`` objects, regardless of which orchestration framework executes it
(LangGraph, CrewAI, ...). These types are pure data + an ABC — no framework
imports live here, so adapters in any framework depend only on this module.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RiskCategory(StrEnum):
    SCHEDULE = "schedule"
    DELIVERY = "delivery"
    QUALITY = "quality"
    DEPENDENCY = "dependency"
    BACKLOG = "backlog"
    RESOURCE = "resource"
    WORKLOAD = "workload"
    RELEASE_READINESS = "release_readiness"
    CROSS_PROJECT = "cross_project"
    PORTFOLIO = "portfolio"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceMetrics(_Frozen):
    """Deterministic, observable facts computed upstream (never by an LLM)."""

    backlog_growth: float = 0.0
    reopen_rate: float = 0.0
    blocker_count: int = 0
    dependency_depth: int = 0
    issue_count: int = 0
    open_issue_count: int = 0
    #: Added facts (default 0 -> backward compatible with older evidence).
    issue_aging_days: float = 0.0           # avg age of open issues
    resolution_velocity: float = 0.0        # issues resolved in the recent window
    resolution_velocity_trend: float = 0.0  # recent window minus prior window (>0 = speeding up)
    contributor_concentration: float = 0.0  # top contributor's share of activity (0-1)
    critical_defect_ratio: float = 0.0      # open blocker/critical issues / open issues (0-1)


class EvidencePackage(_Frozen):
    """Bounded evidence handed to an agent. Small by construction — raw records
    are never included."""

    project_key: str
    project_name: str
    metrics: EvidenceMetrics
    observations: list[str] = Field(default_factory=list)


class RiskFinding(_Frozen):
    """A validated risk finding (see README 'Every material risk finding')."""

    risk_category: RiskCategory
    probability: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0, le=1.0)
    severity: Severity
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    assumptions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    affected: list[str] = Field(default_factory=list)
    source_agent: str
    analysis_timestamp: datetime
    #: Annotations added by review-pipeline processors (validation, correlation,
    #: scoring, critic). Detectors leave this empty.
    meta: dict = Field(default_factory=dict)


class RiskAgent(ABC):
    """Port implemented by every framework adapter of a specialist agent."""

    #: Stable key matching the Admin-API agent config (e.g. "schedule_risk").
    agent_key: str
    #: Primary risk category this agent reasons about.
    category: RiskCategory

    @abstractmethod
    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        """Interpret the evidence and return zero or more risk findings."""


def risk_score(probability: float, impact: float) -> float:
    """Deterministic overall score (0-100) from probability and impact.

    Shared by every agent + framework adapter so findings score identically
    regardless of orchestration.
    """
    p = max(0.0, min(1.0, probability))
    i = max(0.0, min(1.0, impact))
    return round(p * i * 100.0, 1)


def severity_from_score(score: float) -> Severity:
    """Map a 0-100 risk score to a severity band."""
    if score >= 75:
        return Severity.CRITICAL
    if score >= 50:
        return Severity.HIGH
    if score >= 25:
        return Severity.MEDIUM
    return Severity.LOW


# --- Review pipeline ports -------------------------------------------------
#
# Detectors turn evidence into findings (RiskAgent, above). The review pipeline
# then refines those findings and reports on them. Two more ports:
#   FindingProcessor: RiskFinding[] -> RiskFinding[]  (validate/dedup/correlate/score/critique)
#   Reporter:         RiskFinding[] -> RiskReport     (mitigation plan / project / executive)


class ReviewContext(_Frozen):
    """Immutable input to a review processor or reporter."""

    project_key: str
    project_name: str
    evidence: EvidencePackage
    findings: list[RiskFinding]

    def with_findings(self, findings: list[RiskFinding]) -> "ReviewContext":
        return self.model_copy(update={"findings": findings})


class ReportKind(StrEnum):
    MITIGATION = "mitigation"
    PROJECT = "project"
    EXECUTIVE = "executive"


class RiskReport(_Frozen):
    """A generated narrative artifact over a project's risk findings."""

    kind: ReportKind
    title: str
    summary: str
    sections: list[dict] = Field(default_factory=list)  # [{"heading":..., "body":...}]
    source_agent: str
    generated_at: datetime


class FindingProcessor(ABC):
    """Refines a set of findings (drop/merge/annotate/rescore). Deterministic or
    LLM-backed; either way it maps findings -> findings."""

    agent_key: str

    @abstractmethod
    def process(self, context: ReviewContext) -> list[RiskFinding]: ...


class Reporter(ABC):
    """Produces a narrative report from a project's findings."""

    agent_key: str

    @abstractmethod
    def report(self, context: ReviewContext) -> RiskReport: ...
