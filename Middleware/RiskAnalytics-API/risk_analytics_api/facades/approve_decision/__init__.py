"""Use case: approve a decision (dry-run / preview only — creates no real tickets)."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import DecisionResponse
from risk_analytics_api.interfaces.facades import ApproveDecisionUseCase
from risk_analytics_api.interfaces.services import DecisionService


class ApproveDecisionFacade(ApproveDecisionUseCase):
    def __init__(self, service: DecisionService) -> None:
        self._service = service

    def execute(self, decision_id: str) -> DecisionResponse:
        return self._service.approve_decision(decision_id)
