"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from agent_core import EvidencePackage

from risk_analytics_api.dtos.requests import StartAnalysisRequest, StartPortfolioAnalysisRequest
from risk_analytics_api.dtos.responses import (
    AnalysisRunListResponse,
    AnalysisRunResponse,
    DashboardActivityResponse,
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


class DashboardService(ABC):
    @abstractmethod
    def activity(self, limit: int) -> DashboardActivityResponse: ...
