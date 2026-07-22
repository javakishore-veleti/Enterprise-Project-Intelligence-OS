"""Use case: list the available forecast subjects (release/component/tag) for a project."""
from __future__ import annotations

from projects_api.dtos.responses import ForecastSubjectsResponse
from projects_api.interfaces.facades import ForecastSubjectsUseCase
from projects_api.interfaces.services import ForecastSubjectsService


class ForecastSubjectsFacade(ForecastSubjectsUseCase):
    def __init__(self, service: ForecastSubjectsService) -> None:
        self._service = service

    def execute(self, project_key: str) -> ForecastSubjectsResponse:
        return self._service.subjects(project_key)
