"""Unit tests for the ingestion operations service against fakes (no DB/Mongo)."""
from __future__ import annotations

import pytest

from ingestion_api.common.exceptions import NotFoundError
from ingestion_api.dtos.common import OperationRecord
from ingestion_api.dtos.requests import (
    AcquireDatasetRequest,
    IndexDatasetRequest,
    ReconcileDatasetRequest,
    ValidateDatasetRequest,
)
from ingestion_api.interfaces.daos import EvidenceCountsGateway, OperationsDao
from ingestion_api.services.operations import DefaultOperationsService


class FakeOperationsDao(OperationsDao):
    def __init__(self):
        self.rows: dict[str, OperationRecord] = {}

    def insert(self, record):
        self.rows[record.operation_id] = record
        return record

    def get(self, operation_id):
        return self.rows.get(operation_id)

    def update_result(self, operation_id, status, result):
        rec = self.rows[operation_id]
        rec = rec.model_copy(update={"status": status, "result": result})
        self.rows[operation_id] = rec
        return rec


class FakeCounts(EvidenceCountsGateway):
    def document_count(self):
        return 1240

    def index_count(self):
        return 8

    def collection_count(self):
        return 6


def _service():
    return DefaultOperationsService(FakeOperationsDao(), FakeCounts())


def test_acquire_creates_completed_operation() -> None:
    rec = _service().acquire(AcquireDatasetRequest(dataset_id="msr", source_url="http://x"))
    assert rec.op_type == "acquisition" and rec.status == "COMPLETED"


def test_verify_and_extract_acquisition() -> None:
    svc = _service()
    rec = svc.acquire(AcquireDatasetRequest(dataset_id="msr"))
    v = svc.verify_acquisition(rec.operation_id, "abc123")
    assert v.result["verified"] is True and v.result["actual_sha256"] == "abc123"
    e = svc.extract_acquisition(rec.operation_id)
    assert e.result["extracted"] is True and e.result["file_count"] == 6


def test_validate_reports_evidence_counts() -> None:
    rec = _service().validate(ValidateDatasetRequest(dataset_id="msr"))
    assert rec.result == {"valid_count": 1240, "invalid_count": 0}


def test_index_reports_index_count() -> None:
    rec = _service().create_indexes(IndexDatasetRequest(dataset_id="msr", targets=["projects"]))
    assert rec.result["indexes_created"] == 8


def test_reconcile_matches_source_and_destination() -> None:
    rec = _service().reconcile(ReconcileDatasetRequest(dataset_id="msr"))
    assert rec.result["source_count"] == rec.result["destination_count"] == 1240
    assert rec.result["mismatches"] == []


def test_get_wrong_type_raises() -> None:
    svc = _service()
    rec = svc.validate(ValidateDatasetRequest(dataset_id="msr"))
    with pytest.raises(NotFoundError):
        svc.get(rec.operation_id, "acquisition")  # exists but wrong type
    with pytest.raises(NotFoundError):
        svc.get("nope", "validation")
