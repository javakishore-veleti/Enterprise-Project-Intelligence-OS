"""Abstract facade contracts. Concrete implementations live in ``facades/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from risk_analytics_api.dtos.requests import StartAnalysisRequest, StartPortfolioAnalysisRequest
from risk_analytics_api.dtos.responses import AnalysisRunResponse


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
