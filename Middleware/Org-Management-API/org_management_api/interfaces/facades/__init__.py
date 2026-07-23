"""Abstract facade contracts. Concrete implementations live in ``facades/``.

A facade implements one complete application use case and is what the API
routers depend on. Facades take one typed request and return one typed
response object; the concrete implementations translate internal records into
the public response DTOs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from org_management_api.dtos.requests import (
    CreateOrganizationRequest,
    MoveOrganizationRequest,
    UpdateOrganizationRequest,
)
from org_management_api.dtos.responses import OrganizationResponse


class ManageOrganizationsUseCase(ABC):
    @abstractmethod
    def create(self, request: CreateOrganizationRequest) -> OrganizationResponse: ...

    @abstractmethod
    def get(self, org_id: str) -> OrganizationResponse: ...

    @abstractmethod
    def update(self, org_id: str, request: UpdateOrganizationRequest) -> OrganizationResponse: ...

    @abstractmethod
    def move(self, org_id: str, request: MoveOrganizationRequest) -> OrganizationResponse: ...
