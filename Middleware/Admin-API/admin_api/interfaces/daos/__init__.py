"""Abstract DAO contracts. Concrete implementations live in ``daos/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from admin_api.dtos.responses import AgentConfigResponse, AuditEventResponse


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
