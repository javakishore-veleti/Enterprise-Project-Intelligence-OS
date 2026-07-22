"""Use case: run a delivery forecast for a project."""
from __future__ import annotations

from risk_analytics_api.dtos.requests import ForecastRequest
from risk_analytics_api.dtos.responses import ForecastResponse
from risk_analytics_api.interfaces.facades import RunForecastUseCase
from risk_analytics_api.interfaces.services import ForecastService


class RunForecastFacade(RunForecastUseCase):
    def __init__(self, service: ForecastService) -> None:
        self._service = service

    def execute(self, request: ForecastRequest) -> ForecastResponse:
        return self._service.forecast(request)
