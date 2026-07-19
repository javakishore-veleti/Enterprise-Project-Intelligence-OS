"""Contract tests for the operations endpoints (fakes; no DB/Mongo).

Asserts the exact response field names the Airflow DAGs poll on.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from ingestion_api.api.dependencies import provide_dataset_operations_facade
from ingestion_api.api.main import create_app
from ingestion_api.dtos.common import OperationRecord
from ingestion_api.facades.dataset_operations import DatasetOperationsFacade
from ingestion_api.interfaces.daos import EvidenceCountsGateway, OperationsDao
from ingestion_api.services.operations import DefaultOperationsService


class _FakeDao(OperationsDao):
    def __init__(self):
        self.rows: dict[str, OperationRecord] = {}

    def insert(self, record):
        self.rows[record.operation_id] = record
        return record

    def get(self, operation_id):
        return self.rows.get(operation_id)

    def update_result(self, operation_id, status, result):
        rec = self.rows[operation_id].model_copy(update={"status": status, "result": result})
        self.rows[operation_id] = rec
        return rec


class _FakeCounts(EvidenceCountsGateway):
    def document_count(self): return 1240
    def index_count(self): return 8
    def collection_count(self): return 6


def _client() -> TestClient:
    app = create_app()
    facade = DatasetOperationsFacade(DefaultOperationsService(_FakeDao(), _FakeCounts()))
    app.dependency_overrides[provide_dataset_operations_facade] = lambda: facade
    return TestClient(app)


def test_acquisition_lifecycle() -> None:
    c = _client()
    created = c.post("/api/v1/ingestion/acquisitions", json={"dataset_id": "msr", "source_url": "http://x"})
    assert created.status_code == 201
    aid = created.json()["acquisition_id"]
    assert created.json()["status"] == "COMPLETED"

    assert c.get(f"/api/v1/ingestion/acquisitions/{aid}").json()["acquisition_id"] == aid

    v = c.post(f"/api/v1/ingestion/acquisitions/{aid}/verify", json={"expected_sha256": "deadbeef"})
    assert v.json()["verified"] is True and v.json()["actual_sha256"] == "deadbeef"

    e = c.post(f"/api/v1/ingestion/acquisitions/{aid}/extract")
    assert e.json()["extracted"] is True and e.json()["file_count"] == 6


def test_validation_endpoint() -> None:
    c = _client()
    r = c.post("/api/v1/ingestion/validations", json={"dataset_id": "msr", "max_invalid": 0})
    assert r.status_code == 201
    body = r.json()
    assert body["validation_id"] and body["status"] == "COMPLETED"
    assert body["valid_count"] == 1240 and body["invalid_count"] == 0


def test_index_endpoint() -> None:
    r = _client().post("/api/v1/ingestion/indexes", json={"dataset_id": "msr", "targets": ["projects"]})
    assert r.status_code == 201
    assert r.json()["index_job_id"] and r.json()["indexes_created"] == 8


def test_reconciliation_endpoint() -> None:
    r = _client().post("/api/v1/ingestion/reconciliations", json={"dataset_id": "msr"})
    assert r.status_code == 201
    body = r.json()
    assert body["reconciliation_id"]
    assert body["source_count"] == body["destination_count"] == 1240
    assert body["mismatches"] == []


def test_get_missing_returns_404() -> None:
    assert _client().get("/api/v1/ingestion/validations/nope").status_code == 404
