"""Dashboard service: assemble recent cross-project activity from the DAO."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import DashboardActivityResponse
from risk_analytics_api.interfaces.daos import DashboardDao
from risk_analytics_api.interfaces.services import DashboardService


class DefaultDashboardService(DashboardService):
    def __init__(self, dashboard_dao: DashboardDao) -> None:
        self._dao = dashboard_dao

    def activity(self, limit: int) -> DashboardActivityResponse:
        return DashboardActivityResponse(
            recent_runs=self._dao.recent_runs(limit),
            recent_findings=self._dao.recent_findings(limit),
            totals=self._dao.totals(),
        )
