"""Unit tests for the ingestion orchestration service using fake collaborators.

No database or Airflow required — the service is tested against in-memory fakes
of its DAO/gateway interfaces, proving the layering is decoupled.
"""
from __future__ import annotations

import pytest

from ingestion_api.common.exceptions import NotFoundError
from ingestion_api.dtos.common import IngestionStatus
from ingestion_api.dtos.requests import StartIngestionRequest
from ingestion_api.dtos.responses import IngestionRunResponse
from ingestion_api.interfaces.daos import AirflowGateway, IngestionTrackingDao
from ingestion_api.services.ingestion_orchestration import (
    DefaultIngestionOrchestrationService,
)


class FakeTrackingDao(IngestionTrackingDao):
    def __init__(self) -> None:
        self.rows: dict[str, IngestionRunResponse] = {}

    def insert_run(self, run: IngestionRunResponse) -> IngestionRunResponse:
        self.rows[run.run_id] = run
        return run

    def get_run(self, run_id: str) -> IngestionRunResponse | None:
        return self.rows.get(run_id)

    def update_status(self, run_id, status):  # pragma: no cover - unused here
        return self.rows.get(run_id)


class FakeAirflow(AirflowGateway):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def trigger_ingestion(self, run_id: str, dataset_id: str) -> str:
        self.calls.append((run_id, dataset_id))
        return f"ref:{run_id}"


def _service() -> tuple[DefaultIngestionOrchestrationService, FakeTrackingDao, FakeAirflow]:
    dao, airflow = FakeTrackingDao(), FakeAirflow()
    return DefaultIngestionOrchestrationService(dao, airflow), dao, airflow


def test_start_run_persists_and_triggers_airflow() -> None:
    service, dao, airflow = _service()

    run = service.start_run(StartIngestionRequest(dataset_id="msr-2022", batch_size=500))

    assert run.status is IngestionStatus.PENDING
    assert run.dataset_id == "msr-2022"
    assert run.batch_size == 500
    assert run.run_id in dao.rows
    assert airflow.calls == [(run.run_id, "msr-2022")]


def test_get_run_returns_persisted_run() -> None:
    service, _, _ = _service()
    started = service.start_run(StartIngestionRequest(dataset_id="msr-2022"))

    fetched = service.get_run(started.run_id)

    assert fetched.run_id == started.run_id


def test_get_run_missing_raises_not_found() -> None:
    service, _, _ = _service()
    with pytest.raises(NotFoundError):
        service.get_run("does-not-exist")
