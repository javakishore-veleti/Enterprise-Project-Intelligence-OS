"""Use case: fetch one persisted forecast by id."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import ForecastResponse
from risk_analytics_api.interfaces.facades import GetForecastUseCase
from risk_analytics_api.interfaces.services import ForecastService


class GetForecastFacade(GetForecastUseCase):
    def __init__(self, service: ForecastService) -> None:
        self._service = service

    def execute(self, forecast_id: str) -> ForecastResponse:
        return self._service.get_forecast(forecast_id)
