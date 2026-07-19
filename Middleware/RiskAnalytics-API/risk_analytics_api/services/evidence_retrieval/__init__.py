"""Evidence retrieval service — deterministic evidence packages for a project."""
from __future__ import annotations

from agent_core import EvidencePackage

from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.interfaces.daos import EvidenceDao
from risk_analytics_api.interfaces.services import EvidenceRetrievalService


class DefaultEvidenceRetrievalService(EvidenceRetrievalService):
    def __init__(self, evidence_dao: EvidenceDao) -> None:
        self._dao = evidence_dao

    def for_project(self, project_key: str) -> EvidencePackage:
        package = self._dao.build_package(project_key)
        if package is None:
            raise NotFoundError(f"no evidence found for project '{project_key}'")
        return package
