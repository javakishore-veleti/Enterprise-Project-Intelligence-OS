"""Use case: compute the ranked early-warning feed (on read, no LLM)."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import EarlyWarningsResponse
from risk_analytics_api.interfaces.facades import GetEarlyWarningsUseCase
from risk_analytics_api.interfaces.services import EarlyWarningService


class GetEarlyWarningsFacade(GetEarlyWarningsUseCase):
    def __init__(self, service: EarlyWarningService) -> None:
        self._service = service

    def execute(self, scope: str | None, limit: int) -> EarlyWarningsResponse:
        return self._service.warnings(scope, limit)
