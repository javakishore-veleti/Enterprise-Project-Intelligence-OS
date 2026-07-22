"""Use case: list the forecast history (newest-first, capped)."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import ForecastsPageResponse
from risk_analytics_api.interfaces.facades import ListForecastsUseCase
from risk_analytics_api.interfaces.services import ForecastService


class ListForecastsFacade(ListForecastsUseCase):
    def __init__(self, service: ForecastService) -> None:
        self._service = service

    def execute(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> ForecastsPageResponse:
        return self._service.list_forecasts(scope, q, limit, offset)
