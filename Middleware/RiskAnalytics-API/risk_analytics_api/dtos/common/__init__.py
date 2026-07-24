"""Common DTO fragments."""
from __future__ import annotations

from enum import StrEnum

from risk_analytics_api.common.models import TypedModel


class AnalysisStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OrgScope(TypedModel):
    """The authoritative project-key set a caller may see, resolved from the
    Org-Management-API (Phase-2 multi-tenancy).

    Semantics (deliberate, mirrors Projects-API): an ``OrgScope`` object being
    *present* means org scoping applies — the allowed keys become an authoritative
    filter on every project-scoped read/run, AND-composed with any existing
    (``scope`` / ``projects=``) narrowing. An *empty* ``project_keys`` therefore
    means the caller sees nothing (correct isolation), NOT everything. The absence
    of an ``OrgScope`` (``None``) means no org headers were supplied (or the org
    API was unreachable) — the legacy behavior is left 100% unchanged.
    """

    project_keys: tuple[str, ...] = ()

    def as_list(self) -> list[str]:
        return list(self.project_keys)

    def allows(self, project_key: str) -> bool:
        return project_key in self.project_keys
