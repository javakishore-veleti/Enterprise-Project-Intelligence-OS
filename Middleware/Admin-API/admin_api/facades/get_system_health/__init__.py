"""Use case: report aggregate system health."""
from __future__ import annotations

from admin_api.dtos.responses import SystemHealthResponse
from admin_api.interfaces.facades import GetSystemHealthUseCase
from admin_api.interfaces.services import SystemHealthService


class GetSystemHealthFacade(GetSystemHealthUseCase):
    def __init__(self, service: SystemHealthService) -> None:
        self._service = service

    def execute(self) -> SystemHealthResponse:
        return self._service.snapshot()
