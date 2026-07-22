"""Use case: fetch one persisted decision by id."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import DecisionResponse
from risk_analytics_api.interfaces.facades import GetDecisionUseCase
from risk_analytics_api.interfaces.services import DecisionService


class GetDecisionFacade(GetDecisionUseCase):
    def __init__(self, service: DecisionService) -> None:
        self._service = service

    def execute(self, decision_id: str) -> DecisionResponse:
        return self._service.get_decision(decision_id)
