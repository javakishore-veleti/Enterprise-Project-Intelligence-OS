"""Use case: list the available investigation templates."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import InvestigationTemplateResponse
from risk_analytics_api.interfaces.facades import ListInvestigationTemplatesUseCase
from risk_analytics_api.interfaces.services import InvestigationService


class ListInvestigationTemplatesFacade(ListInvestigationTemplatesUseCase):
    def __init__(self, service: InvestigationService) -> None:
        self._service = service

    def execute(self) -> list[InvestigationTemplateResponse]:
        return self._service.list_templates()
