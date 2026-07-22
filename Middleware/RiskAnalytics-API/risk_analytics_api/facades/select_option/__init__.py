"""Use case: select one of a decision's generated options."""
from __future__ import annotations

from risk_analytics_api.dtos.requests import SelectOptionRequest
from risk_analytics_api.dtos.responses import DecisionResponse
from risk_analytics_api.interfaces.facades import SelectOptionUseCase
from risk_analytics_api.interfaces.services import DecisionService


class SelectOptionFacade(SelectOptionUseCase):
    def __init__(self, service: DecisionService) -> None:
        self._service = service

    def execute(self, decision_id: str, request: SelectOptionRequest) -> DecisionResponse:
        return self._service.select_option(decision_id, request)
