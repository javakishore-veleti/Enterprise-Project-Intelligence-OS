"""Contract tests for the HTTP surface.

DB and Airflow dependencies are overridden with in-memory fakes so the test
exercises routing, validation, serialization, and error mapping without infra.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from ingestion_api.api.dependencies import (
    provide_get_ingestion_status_facade,
    provide_start_ingestion_facade,
)
from ingestion_api.api.main import create_app
from ingestion_api.dtos.requests import StartIngestionRequest
from ingestion_api.dtos.responses import IngestionRunResponse
from ingestion_api.facades.get_ingestion_status import GetIngestionStatusFacade
from ingestion_api.facades.start_ingestion import StartIngestionFacade
from ingestion_api.interfaces.daos import AirflowGateway, IngestionTrackingDao
from ingestion_api.services.ingestion_orchestration import (
    DefaultIngestionOrchestrationService,
)


class _FakeDao(IngestionTrackingDao):
    def __init__(self) -> None:
        self.rows: dict[str, IngestionRunResponse] = {}

    def insert_run(self, run):
        self.rows[run.run_id] = run
        return run

    def get_run(self, run_id):
        return self.rows.get(run_id)

    def update_status(self, run_id, status):
        return self.rows.get(run_id)

    def latest_run_for_dataset(self, dataset_id):
        return None


class _FakeAirflow(AirflowGateway):
    def trigger_ingestion(self, run_id, dataset_id):
        return f"ref:{run_id}"


def _client() -> TestClient:
    app = create_app()
    service = DefaultIngestionOrchestrationService(_FakeDao(), _FakeAirflow())
    app.dependency_overrides[provide_start_ingestion_facade] = lambda: StartIngestionFacade(service)
    app.dependency_overrides[provide_get_ingestion_status_facade] = (
        lambda: GetIngestionStatusFacade(service)
    )
    return TestClient(app)


def test_liveness_ok() -> None:
    resp = _client().get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_start_then_get_roundtrip() -> None:
    client = _client()

    created = client.post("/api/v1/ingestion/runs", json={"dataset_id": "msr-2022"})
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "PENDING"
    run_id = body["run_id"]

    fetched = client.get(f"/api/v1/ingestion/runs/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run_id


def test_get_missing_returns_404_with_error_envelope() -> None:
    resp = _client().get("/api/v1/ingestion/runs/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_invalid_request_returns_422() -> None:
    resp = _client().post("/api/v1/ingestion/runs", json={"dataset_id": ""})
    assert resp.status_code == 422
