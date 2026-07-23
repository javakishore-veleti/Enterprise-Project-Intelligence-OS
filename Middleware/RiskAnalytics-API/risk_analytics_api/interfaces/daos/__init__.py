"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from agent_core import EvidencePackage, RiskFinding, RiskReport

from datetime import datetime

from risk_analytics_api.dtos.responses import (
    AnalysisRunResponse,
    AnalysisRunSummary,
    AttentionFindingRow,
    DashboardFindingSummary,
    DashboardTotals,
    DecisionRecord,
    DecisionResponse,
    DecisionsPageResponse,
    ForecastRecord,
    ForecastResponse,
    ForecastsPageResponse,
    InvestigationRecord,
    InvestigationResponse,
    InvestigationsPageResponse,
    ReportResponse,
    ScenarioRecord,
    ScenarioResponse,
    ScenariosPageResponse,
)


class AgentConfigGateway(ABC):
    """Read-only view of Admin-API agent configuration (framework/model/enabled)."""

    @abstractmethod
    def get(self, agent_key: str) -> tuple[bool, str, str] | None:
        """Return (enabled, model, framework) or None if unconfigured."""


class EvidenceDao(ABC):
    """Builds a bounded, deterministic evidence package from the evidence store."""

    @abstractmethod
    def build_package(self, project_key: str) -> EvidencePackage | None: ...

    @abstractmethod
    def list_project_keys(self, limit: int) -> list[str]:
        """Return up to ``limit`` project keys (for portfolio resolution)."""


class GraphRunDao(ABC):
    """Persistence of analysis runs (PostgreSQL)."""

    @abstractmethod
    def create(self, run_id: str, project_key: str, agent_keys: list[str], started_at) -> None: ...

    @abstractmethod
    def complete(self, run_id: str, status: str, finished_at) -> None: ...

    @abstractmethod
    def get(self, run_id: str) -> AnalysisRunResponse | None:
        """Return the run with its findings, or None."""

    @abstractmethod
    def list_for_project(self, project_key: str, limit: int) -> list["AnalysisRunSummary"]:
        """Recent run summaries (with finding/report counts) for a project, newest first."""


class DashboardDao(ABC):
    """Cross-project reads for the dashboard activity feed (PostgreSQL)."""

    @abstractmethod
    def recent_runs(self, limit: int) -> list["AnalysisRunSummary"]:
        """Recent run summaries (with finding/report counts) across all projects, newest first."""

    @abstractmethod
    def recent_findings(self, limit: int) -> list["DashboardFindingSummary"]:
        """Most recent findings across all projects, newest first."""

    @abstractmethod
    def totals(self) -> "DashboardTotals":
        """Total run count, finding count, and distinct-project count."""


class AttentionDao(ABC):
    """Scoped, time-aware cross-project reads for the attention feed (PostgreSQL)."""

    @abstractmethod
    def count(self, as_of_end: datetime | None, projects: list[str] | None) -> int:
        """Total in-scope findings matching the as_of upper bound + project scope."""

    @abstractmethod
    def distinct_projects(self, as_of_end: datetime | None, projects: list[str] | None) -> int:
        """Count of distinct project_keys among in-scope findings."""

    @abstractmethod
    def window(
        self, as_of_end: datetime | None, projects: list[str] | None, cap: int
    ) -> list["AttentionFindingRow"]:
        """In-scope findings ordered by analysis_timestamp DESC, limited to ``cap``."""


class RiskFindingDao(ABC):
    """Persistence of risk findings (PostgreSQL)."""

    @abstractmethod
    def add_many(self, run_id: str, project_key: str, findings: list[RiskFinding]) -> list[str]:
        """Persist findings; return the new finding ids."""

    @abstractmethod
    def list_for_run(self, run_id: str) -> list["RiskFindingResponse"]:
        """Return the persisted findings for a run."""


class ReportDao(ABC):
    """Persistence of generated review reports (PostgreSQL)."""

    @abstractmethod
    def add_many(self, run_id: str, project_key: str, reports: list[RiskReport]) -> list[str]: ...

    @abstractmethod
    def list_for_run(self, run_id: str) -> list[ReportResponse]: ...


class InvestigationDao(ABC):
    """Persistence of Investigation Agent runs (PostgreSQL)."""

    @abstractmethod
    def insert_investigation(self, record: InvestigationRecord) -> None:
        """Persist one full investigation row."""

    @abstractmethod
    def list_investigations(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> InvestigationsPageResponse:
        """Newest-first history page. Filters by ``scope`` (requested_by), a
        case-insensitive ``q`` across project_key/question/root_cause, and an
        optional ``projects`` list (``project_key IN (...)``). The list and total
        are capped at the newest 100."""

    @abstractmethod
    def get_investigation(self, investigation_id: str) -> InvestigationResponse | None:
        """Return one full investigation, or None if absent."""


class ForecastDao(ABC):
    """Persistence of delivery-forecast runs (PostgreSQL)."""

    @abstractmethod
    def insert_forecast(self, record: ForecastRecord) -> None:
        """Persist one full forecast row."""

    @abstractmethod
    def list_forecasts(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> ForecastsPageResponse:
        """Newest-first history page. Filters by ``scope`` (requested_by), a
        case-insensitive ``q`` across project_key/narrative, and an optional
        ``projects`` list (``project_key IN (...)``). Capped at the newest 100."""

    @abstractmethod
    def get_forecast(self, forecast_id: str) -> ForecastResponse | None:
        """Return one full forecast, or None if absent."""


class ScenarioDao(ABC):
    """Persistence of digital-twin scenario runs (PostgreSQL)."""

    @abstractmethod
    def insert_scenario(self, record: ScenarioRecord) -> None:
        """Persist one full scenario row."""

    @abstractmethod
    def list_scenarios(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> ScenariosPageResponse:
        """Newest-first history page. Filters by ``scope`` (requested_by), a
        case-insensitive ``q`` across project_key/scenario/narrative, and an
        optional ``projects`` list (``project_key IN (...)``). Capped at the newest 100."""

    @abstractmethod
    def get_scenario(self, scenario_id: str) -> ScenarioResponse | None:
        """Return one full scenario, or None if absent."""


class DecisionDao(ABC):
    """Persistence of Decide runs — Options-first decision support (PostgreSQL)."""

    @abstractmethod
    def insert_decision(self, record: DecisionRecord) -> None:
        """Persist one full decision row (DRAFTED on create, FAILED on agent error)."""

    @abstractmethod
    def update_selection(self, decision_id: str, option_id: str, status: str) -> None:
        """Set the selected option id + status (SELECTED)."""

    @abstractmethod
    def update_approval(self, decision_id: str, status: str, approved_at: datetime) -> None:
        """Set the status (APPROVED) + approved_at timestamp."""

    @abstractmethod
    def list_decisions(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> DecisionsPageResponse:
        """Newest-first history page. Filters by ``scope`` (requested_by), a
        case-insensitive ``q`` across project_key/narrative, and an optional
        ``projects`` list (``project_key IN (...)``). Capped at the newest 100."""

    @abstractmethod
    def get_decision(self, decision_id: str) -> DecisionResponse | None:
        """Return one full decision, or None if absent."""
