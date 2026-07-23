"""Use case: list the scenario history (newest-first, capped)."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import ScenariosPageResponse
from risk_analytics_api.interfaces.facades import ListScenariosUseCase
from risk_analytics_api.interfaces.services import ScenarioService


class ListScenariosFacade(ListScenariosUseCase):
    def __init__(self, service: ScenarioService) -> None:
        self._service = service

    def execute(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> ScenariosPageResponse:
        return self._service.list_scenarios(scope, q, limit, offset, projects)
