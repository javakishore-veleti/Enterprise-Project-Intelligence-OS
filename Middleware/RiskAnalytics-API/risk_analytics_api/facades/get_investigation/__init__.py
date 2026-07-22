"""Use case: fetch one persisted investigation by id."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import InvestigationResponse
from risk_analytics_api.interfaces.facades import GetInvestigationUseCase
from risk_analytics_api.interfaces.services import InvestigationService


class GetInvestigationFacade(GetInvestigationUseCase):
    def __init__(self, service: InvestigationService) -> None:
        self._service = service

    def execute(self, investigation_id: str) -> InvestigationResponse:
        return self._service.get_investigation(investigation_id)
