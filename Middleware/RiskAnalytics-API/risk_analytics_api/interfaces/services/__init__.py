"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from agent_core import EvidencePackage

from risk_analytics_api.dtos.requests import (
    DecisionRequest,
    ForecastRequest,
    InvestigateRequest,
    ScenarioRequest,
    SelectOptionRequest,
    StartAnalysisRequest,
    StartPortfolioAnalysisRequest,
)
from risk_analytics_api.dtos.responses import (
    AnalysisRunListResponse,
    AnalysisRunResponse,
    AttentionResponse,
    DashboardActivityResponse,
    DecisionResponse,
    DecisionsPageResponse,
    EarlyWarningsResponse,
    ForecastResponse,
    ForecastsPageResponse,
    InvestigationResponse,
    InvestigationsPageResponse,
    InvestigationTemplateResponse,
    ScenarioResponse,
    ScenariosPageResponse,
)


class EvidenceRetrievalService(ABC):
    @abstractmethod
    def for_project(self, project_key: str) -> EvidencePackage: ...

    @abstractmethod
    def list_project_keys(self, limit: int) -> list[str]: ...


class AnalysisOrchestrationService(ABC):
    @abstractmethod
    def run(self, project_key: str, request: StartAnalysisRequest) -> AnalysisRunResponse: ...

    @abstractmethod
    def run_portfolio(
        self, portfolio_key: str, request: StartPortfolioAnalysisRequest
    ) -> AnalysisRunResponse: ...

    @abstractmethod
    def get_run(self, run_id: str) -> AnalysisRunResponse: ...

    @abstractmethod
    def list_runs(self, project_key: str, limit: int) -> AnalysisRunListResponse: ...


class InvestigationService(ABC):
    @abstractmethod
    def investigate(self, request: InvestigateRequest) -> InvestigationResponse:
        """Run the autonomous Investigation Agent, persist it, and return its conclusion."""

    @abstractmethod
    def list_investigations(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> InvestigationsPageResponse:
        """Newest-first history page (capped at the newest 100)."""

    @abstractmethod
    def get_investigation(self, investigation_id: str) -> InvestigationResponse:
        """Return one persisted investigation, or raise NotFoundError."""

    @abstractmethod
    def list_templates(self) -> list[InvestigationTemplateResponse]:
        """The available investigation templates."""


class ForecastService(ABC):
    @abstractmethod
    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        """Compute the deterministic forecast, narrate it, persist it, and return it."""

    @abstractmethod
    def list_forecasts(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> ForecastsPageResponse:
        """Newest-first history page (capped at the newest 100)."""

    @abstractmethod
    def get_forecast(self, forecast_id: str) -> ForecastResponse:
        """Return one persisted forecast, or raise NotFoundError."""


class ScenarioService(ABC):
    @abstractmethod
    def simulate(self, request: ScenarioRequest) -> ScenarioResponse:
        """Re-forecast under the what-if, propagate the cascade, narrate, persist, return."""

    @abstractmethod
    def list_scenarios(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> ScenariosPageResponse:
        """Newest-first history page (capped at the newest 100)."""

    @abstractmethod
    def get_scenario(self, scenario_id: str) -> ScenarioResponse:
        """Return one persisted scenario, or raise NotFoundError."""


class DecisionService(ABC):
    @abstractmethod
    def decide(self, request: DecisionRequest) -> DecisionResponse:
        """Generate 2-3 decision options, persist DRAFTED, and return the decision."""

    @abstractmethod
    def select_option(self, decision_id: str, request: SelectOptionRequest) -> DecisionResponse:
        """Set the chosen option (status SELECTED); its actions + owners are the plan."""

    @abstractmethod
    def approve_decision(self, decision_id: str) -> DecisionResponse:
        """Record approval (status APPROVED) as a dry-run/preview — creates no real tickets."""

    @abstractmethod
    def list_decisions(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> DecisionsPageResponse:
        """Newest-first history page (capped at the newest 100)."""

    @abstractmethod
    def get_decision(self, decision_id: str) -> DecisionResponse:
        """Return one persisted decision, or raise NotFoundError."""


class EarlyWarningService(ABC):
    @abstractmethod
    def warnings(self, scope: str | None, limit: int) -> EarlyWarningsResponse:
        """Detect + rank adverse metric inflections across the in-scope projects.

        Computed on read (no LLM, no persistence) so it is fast + always-on.
        """


class DashboardService(ABC):
    @abstractmethod
    def activity(self, limit: int) -> DashboardActivityResponse: ...


class AttentionService(ABC):
    @abstractmethod
    def feed(
        self,
        *,
        top: int,
        offset: int,
        as_of: str | None,
        as_of_end: datetime | None,
        projects: list[str] | None,
        now: datetime,
    ) -> AttentionResponse:
        """Rank, sort, and paginate the in-scope findings into an attention feed.

        ``now`` is the reference instant for recency scoring (injected so the
        scoring stays deterministic and testable).
        """
