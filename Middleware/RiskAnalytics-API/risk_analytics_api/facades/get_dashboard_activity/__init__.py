"""Use case: recent cross-project activity for the dashboard."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import DashboardActivityResponse
from risk_analytics_api.interfaces.facades import GetDashboardActivityUseCase
from risk_analytics_api.interfaces.services import DashboardService


class GetDashboardActivityFacade(GetDashboardActivityUseCase):
    def __init__(self, service: DashboardService) -> None:
        self._service = service

    def execute(
        self, limit: int, projects: list[str] | None = None
    ) -> DashboardActivityResponse:
        return self._service.activity(limit, projects)
