"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from admin_api.dtos.dataset import DatasetStatusResponse, IngestionProgressResponse
from admin_api.dtos.responses import AgentConfigResponse, AuditEventResponse


class DatasetGateway(ABC):
    """Governed boundary to the Ingestion API for dataset acquisition + ingestion."""

    @abstractmethod
    def get_status(self, dataset_id: str) -> DatasetStatusResponse: ...

    @abstractmethod
    def trigger_download(self, dataset_id: str) -> DatasetStatusResponse: ...

    @abstractmethod
    def get_ingestion(self, dataset_id: str) -> IngestionProgressResponse: ...

    @abstractmethod
    def trigger_ingest(self, dataset_id: str) -> IngestionProgressResponse: ...


class AgentConfigDao(ABC):
    """Persistence of agent runtime configuration (PostgreSQL)."""

    @abstractmethod
    def list(self, limit: int, offset: int) -> tuple[list[AgentConfigResponse], int]: ...

    @abstractmethod
    def get(self, agent_key: str) -> AgentConfigResponse | None: ...

    @abstractmethod
    def upsert(self, config: AgentConfigResponse) -> AgentConfigResponse: ...

    @abstractmethod
    def counts(self) -> tuple[int, int]:
        """Return (total agents, enabled agents)."""


class AuditDao(ABC):
    """Append-only administrative audit log (PostgreSQL)."""

    @abstractmethod
    def append(self, event: AuditEventResponse) -> AuditEventResponse: ...

    @abstractmethod
    def list(self, limit: int, offset: int) -> tuple[list[AuditEventResponse], int]: ...
