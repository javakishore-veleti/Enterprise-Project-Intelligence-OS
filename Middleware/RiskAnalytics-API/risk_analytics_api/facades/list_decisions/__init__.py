"""Use case: list the decision history (newest-first, capped)."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import DecisionsPageResponse
from risk_analytics_api.interfaces.facades import ListDecisionsUseCase
from risk_analytics_api.interfaces.services import DecisionService


class ListDecisionsFacade(ListDecisionsUseCase):
    def __init__(self, service: DecisionService) -> None:
        self._service = service

    def execute(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> DecisionsPageResponse:
        return self._service.list_decisions(scope, q, limit, offset, projects)
