"""Forecast-subjects service — the selectable release/component/tag values.

Validates the project exists (404 otherwise, mirroring the metrics endpoints),
then delegates to the faceting DAO. Capped at the top ``SUBJECT_CAP`` values per
facet so the subject picker stays bounded.
"""
from __future__ import annotations

from projects_api.common.exceptions import NotFoundError
from projects_api.dtos.responses import ForecastSubjectsResponse
from projects_api.interfaces.daos import ForecastSubjectsDao, ProjectsDao
from projects_api.interfaces.services import ForecastSubjectsService

#: Top-N values returned per facet (release / component / tag).
SUBJECT_CAP = 50


class DefaultForecastSubjectsService(ForecastSubjectsService):
    def __init__(self, subjects_dao: ForecastSubjectsDao, projects_dao: ProjectsDao) -> None:
        self._dao = subjects_dao
        self._projects = projects_dao

    def subjects(self, project_key: str) -> ForecastSubjectsResponse:
        if self._projects.get(project_key) is None:
            raise NotFoundError(f"project '{project_key}' not found")
        return self._dao.facets(project_key, SUBJECT_CAP)
