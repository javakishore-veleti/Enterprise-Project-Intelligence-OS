"""Use case: run Options-first decision support for a project."""
from __future__ import annotations

from risk_analytics_api.dtos.requests import DecisionRequest
from risk_analytics_api.dtos.responses import DecisionResponse
from risk_analytics_api.interfaces.facades import RunDecisionUseCase
from risk_analytics_api.interfaces.services import DecisionService


class RunDecisionFacade(RunDecisionUseCase):
    def __init__(self, service: DecisionService) -> None:
        self._service = service

    def execute(self, request: DecisionRequest) -> DecisionResponse:
        return self._service.decide(request)
