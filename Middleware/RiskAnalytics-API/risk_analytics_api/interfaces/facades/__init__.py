"""Abstract facade contracts. Concrete implementations live in ``facades/``."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

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


class StartProjectAnalysisUseCase(ABC):
    @abstractmethod
    def execute(self, project_key: str, request: StartAnalysisRequest) -> AnalysisRunResponse: ...


class StartPortfolioAnalysisUseCase(ABC):
    @abstractmethod
    def execute(
        self, portfolio_key: str, request: StartPortfolioAnalysisRequest
    ) -> AnalysisRunResponse: ...


class GetAnalysisRunUseCase(ABC):
    @abstractmethod
    def execute(self, run_id: str) -> AnalysisRunResponse: ...


class GetDashboardActivityUseCase(ABC):
    @abstractmethod
    def execute(
        self, limit: int, projects: list[str] | None = None
    ) -> DashboardActivityResponse: ...


class GetAttentionFeedUseCase(ABC):
    @abstractmethod
    def execute(
        self, top: int, as_of: date | None, projects: list[str] | None, offset: int
    ) -> AttentionResponse: ...


class InvestigateProjectUseCase(ABC):
    @abstractmethod
    def execute(self, request: InvestigateRequest) -> InvestigationResponse: ...


class ListInvestigationsUseCase(ABC):
    @abstractmethod
    def execute(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> InvestigationsPageResponse: ...


class GetInvestigationUseCase(ABC):
    @abstractmethod
    def execute(self, investigation_id: str) -> InvestigationResponse: ...


class ListInvestigationTemplatesUseCase(ABC):
    @abstractmethod
    def execute(self) -> list[InvestigationTemplateResponse]: ...


class RunForecastUseCase(ABC):
    @abstractmethod
    def execute(self, request: ForecastRequest) -> ForecastResponse: ...


class ListForecastsUseCase(ABC):
    @abstractmethod
    def execute(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> ForecastsPageResponse: ...


class GetForecastUseCase(ABC):
    @abstractmethod
    def execute(self, forecast_id: str) -> ForecastResponse: ...


class RunScenarioUseCase(ABC):
    @abstractmethod
    def execute(self, request: ScenarioRequest) -> ScenarioResponse: ...


class ListScenariosUseCase(ABC):
    @abstractmethod
    def execute(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> ScenariosPageResponse: ...


class GetScenarioUseCase(ABC):
    @abstractmethod
    def execute(self, scenario_id: str) -> ScenarioResponse: ...


class RunDecisionUseCase(ABC):
    @abstractmethod
    def execute(self, request: DecisionRequest) -> DecisionResponse: ...


class SelectOptionUseCase(ABC):
    @abstractmethod
    def execute(self, decision_id: str, request: SelectOptionRequest) -> DecisionResponse: ...


class ApproveDecisionUseCase(ABC):
    @abstractmethod
    def execute(self, decision_id: str) -> DecisionResponse: ...


class ListDecisionsUseCase(ABC):
    @abstractmethod
    def execute(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> DecisionsPageResponse: ...


class GetDecisionUseCase(ABC):
    @abstractmethod
    def execute(self, decision_id: str) -> DecisionResponse: ...


class GetEarlyWarningsUseCase(ABC):
    @abstractmethod
    def execute(self, scope: str | None, limit: int) -> EarlyWarningsResponse: ...
