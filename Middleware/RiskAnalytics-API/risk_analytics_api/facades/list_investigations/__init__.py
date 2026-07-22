"""Use case: list the investigation history (newest-first, capped)."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import InvestigationsPageResponse
from risk_analytics_api.interfaces.facades import ListInvestigationsUseCase
from risk_analytics_api.interfaces.services import InvestigationService


class ListInvestigationsFacade(ListInvestigationsUseCase):
    def __init__(self, service: InvestigationService) -> None:
        self._service = service

    def execute(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> InvestigationsPageResponse:
        return self._service.list_investigations(scope, q, limit, offset)
