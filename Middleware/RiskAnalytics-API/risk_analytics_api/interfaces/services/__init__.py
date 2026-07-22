"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from agent_core import EvidencePackage

from risk_analytics_api.dtos.requests import StartAnalysisRequest, StartPortfolioAnalysisRequest
from risk_analytics_api.dtos.responses import (
    AnalysisRunListResponse,
    AnalysisRunResponse,
    AttentionResponse,
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
