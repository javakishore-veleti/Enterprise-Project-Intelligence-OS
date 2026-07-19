"""Abstract facade contracts. Concrete implementations live in ``facades/``."""
from __future__ import annotations

from abc import ABC, abstractmethod

from admin_api.dtos.requests import UpsertAgentConfigRequest
from admin_api.dtos.responses import (
    AgentConfigListResponse,
    AgentConfigResponse,
    AuditListResponse,
    SystemHealthResponse,
)


class ManageAgentsUseCase(ABC):
    @abstractmethod
    def list(self, limit: int, offset: int) -> AgentConfigListResponse: ...

    @abstractmethod
    def get(self, agent_key: str) -> AgentConfigResponse: ...

    @abstractmethod
    def upsert(self, agent_key: str, request: UpsertAgentConfigRequest) -> AgentConfigResponse: ...


class GetAuditHistoryUseCase(ABC):
    @abstractmethod
    def execute(self, limit: int, offset: int) -> AuditListResponse: ...


class GetSystemHealthUseCase(ABC):
    @abstractmethod
    def execute(self) -> SystemHealthResponse: ...
