"""Use case: run the autonomous Investigation Agent over a project."""
from __future__ import annotations

from risk_analytics_api.dtos.requests import InvestigateRequest
from risk_analytics_api.dtos.responses import InvestigationResponse
from risk_analytics_api.interfaces.facades import InvestigateProjectUseCase
from risk_analytics_api.interfaces.services import InvestigationService


class InvestigateProjectFacade(InvestigateProjectUseCase):
    def __init__(self, service: InvestigationService) -> None:
        self._service = service

    def execute(self, request: InvestigateRequest) -> InvestigationResponse:
        return self._service.investigate(request)
