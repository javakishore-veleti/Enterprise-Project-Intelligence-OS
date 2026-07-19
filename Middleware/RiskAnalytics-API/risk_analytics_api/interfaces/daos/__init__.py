"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from agent_core import EvidencePackage, RiskFinding, RiskReport

from risk_analytics_api.dtos.responses import AnalysisRunResponse, ReportResponse


class AgentConfigGateway(ABC):
    """Read-only view of Admin-API agent configuration (framework/model/enabled)."""

    @abstractmethod
    def get(self, agent_key: str) -> tuple[bool, str, str] | None:
        """Return (enabled, model, framework) or None if unconfigured."""


class EvidenceDao(ABC):
    """Builds a bounded, deterministic evidence package from the evidence store."""

    @abstractmethod
    def build_package(self, project_key: str) -> EvidencePackage | None: ...

    @abstractmethod
    def list_project_keys(self, limit: int) -> list[str]:
        """Return up to ``limit`` project keys (for portfolio resolution)."""


class GraphRunDao(ABC):
    """Persistence of analysis runs (PostgreSQL)."""

    @abstractmethod
    def create(self, run_id: str, project_key: str, agent_keys: list[str], started_at) -> None: ...

    @abstractmethod
    def complete(self, run_id: str, status: str, finished_at) -> None: ...

    @abstractmethod
    def get(self, run_id: str) -> AnalysisRunResponse | None:
        """Return the run with its findings, or None."""


class RiskFindingDao(ABC):
    """Persistence of risk findings (PostgreSQL)."""

    @abstractmethod
    def add_many(self, run_id: str, project_key: str, findings: list[RiskFinding]) -> list[str]:
        """Persist findings; return the new finding ids."""

    @abstractmethod
    def list_for_run(self, run_id: str) -> list["RiskFindingResponse"]:
        """Return the persisted findings for a run."""


class ReportDao(ABC):
    """Persistence of generated review reports (PostgreSQL)."""

    @abstractmethod
    def add_many(self, run_id: str, project_key: str, reports: list[RiskReport]) -> list[str]: ...

    @abstractmethod
    def list_for_run(self, run_id: str) -> list[ReportResponse]: ...
