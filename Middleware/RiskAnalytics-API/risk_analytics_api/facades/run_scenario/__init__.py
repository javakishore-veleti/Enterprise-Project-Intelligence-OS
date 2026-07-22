"""Use case: run a digital-twin what-if scenario for a project."""
from __future__ import annotations

from risk_analytics_api.dtos.requests import ScenarioRequest
from risk_analytics_api.dtos.responses import ScenarioResponse
from risk_analytics_api.interfaces.facades import RunScenarioUseCase
from risk_analytics_api.interfaces.services import ScenarioService


class RunScenarioFacade(RunScenarioUseCase):
    def __init__(self, service: ScenarioService) -> None:
        self._service = service

    def execute(self, request: ScenarioRequest) -> ScenarioResponse:
        return self._service.simulate(request)
