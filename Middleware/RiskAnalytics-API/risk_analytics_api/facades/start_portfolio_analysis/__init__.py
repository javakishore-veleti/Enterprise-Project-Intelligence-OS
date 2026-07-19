"""Use case: start a portfolio (multi-project) risk analysis."""
from __future__ import annotations

from risk_analytics_api.dtos.requests import StartPortfolioAnalysisRequest
from risk_analytics_api.dtos.responses import AnalysisRunResponse
from risk_analytics_api.interfaces.facades import StartPortfolioAnalysisUseCase
from risk_analytics_api.interfaces.services import AnalysisOrchestrationService


class StartPortfolioAnalysisFacade(StartPortfolioAnalysisUseCase):
    def __init__(self, service: AnalysisOrchestrationService) -> None:
        self._service = service

    def execute(
        self, portfolio_key: str, request: StartPortfolioAnalysisRequest
    ) -> AnalysisRunResponse:
        return self._service.run_portfolio(portfolio_key, request)
