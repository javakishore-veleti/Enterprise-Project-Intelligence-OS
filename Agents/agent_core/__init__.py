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


class RiskAgent(ABC):
    """Port implemented by every framework adapter of a specialist agent."""

    #: Stable key matching the Admin-API agent config (e.g. "schedule_risk").
    agent_key: str
    #: Primary risk category this agent reasons about.
    category: RiskCategory

    @abstractmethod
    def analyze(self, evidence: EvidencePackage) -> list[RiskFinding]:
        """Interpret the evidence and return zero or more risk findings."""
