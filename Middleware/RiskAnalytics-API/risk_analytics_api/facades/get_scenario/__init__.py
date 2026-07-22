"""Use case: fetch one persisted scenario by id."""
from __future__ import annotations

from risk_analytics_api.dtos.responses import ScenarioResponse
from risk_analytics_api.interfaces.facades import GetScenarioUseCase
from risk_analytics_api.interfaces.services import ScenarioService


class GetScenarioFacade(GetScenarioUseCase):
    def __init__(self, service: ScenarioService) -> None:
        self._service = service

    def execute(self, scenario_id: str) -> ScenarioResponse:
        return self._service.get_scenario(scenario_id)
