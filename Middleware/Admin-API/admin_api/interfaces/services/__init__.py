"""Abstract service contracts. Concrete implementations live in ``services/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from admin_api.dtos.requests import UpsertAgentConfigRequest
from admin_api.dtos.responses import (
    AgentConfigListResponse,
    AgentConfigResponse,
    AuditListResponse,
    SystemHealthResponse,
)


class AgentManagementService(ABC):
    @abstractmethod
    def list(self, limit: int, offset: int) -> AgentConfigListResponse: ...

    @abstractmethod
    def get(self, agent_key: str) -> AgentConfigResponse: ...

    @abstractmethod
    def upsert(self, agent_key: str, request: UpsertAgentConfigRequest) -> AgentConfigResponse: ...


class AuditManagementService(ABC):
    @abstractmethod
    def list(self, limit: int, offset: int, q: str | None = None) -> AuditListResponse: ...


class SystemHealthService(ABC):
    @abstractmethod
    def snapshot(self) -> SystemHealthResponse: ...
