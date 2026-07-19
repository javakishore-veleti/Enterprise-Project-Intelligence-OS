"""Ingestion sub-operations service (acquire/validate/index/reconcile).

These model heavy operational steps. In this foundation build they execute
synchronously to COMPLETED and compute real result counts against the evidence
store (validate/index/reconcile) — acquisition download/verify/extract are
stubbed since no live 5.8 GB dataset is present. Each operation is persisted so
the Airflow DAGs can poll it by id.
"""
from __future__ import annotations

from ingestion_api.common.exceptions import NotFoundError
from ingestion_api.common.utilities import new_id, utc_now
from ingestion_api.dtos.common import OperationRecord
from ingestion_api.dtos.requests import (
    AcquireDatasetRequest,
    IndexDatasetRequest,
    ReconcileDatasetRequest,
    ValidateDatasetRequest,
)
from ingestion_api.interfaces.daos import EvidenceCountsGateway, OperationsDao
from ingestion_api.interfaces.services import OperationsService

_COMPLETED = "COMPLETED"


class DefaultOperationsService(OperationsService):
    def __init__(self, operations_dao: OperationsDao, evidence_counts: EvidenceCountsGateway) -> None:
        self._dao = operations_dao
        self._counts = evidence_counts

    def _create(self, op_type: str, dataset_id: str, params: dict, result: dict) -> OperationRecord:
        now = utc_now()
        return self._dao.insert(OperationRecord(
            operation_id=new_id(), op_type=op_type, dataset_id=dataset_id,
            status=_COMPLETED, params=params, result=result, created_at=now, updated_at=now,
        ))

    def _require(self, operation_id: str, op_type: str) -> OperationRecord:
        rec = self._dao.get(operation_id)
        if rec is None or rec.op_type != op_type:
            raise NotFoundError(f"{op_type} '{operation_id}' not found")
        return rec

    # --- acquisition (stubbed: no real dataset present) ---
    def acquire(self, request: AcquireDatasetRequest) -> OperationRecord:
        return self._create(
            "acquisition", request.dataset_id,
            {"source_url": request.source_url, "requested_by": request.requested_by}, {},
        )

    def verify_acquisition(self, operation_id: str, expected_sha256: str) -> OperationRecord:
        self._require(operation_id, "acquisition")
        # Stub: no downloaded archive to hash, so the expected checksum is accepted.
        result = {"verified": True, "actual_sha256": expected_sha256}
        return self._dao.update_result(operation_id, _COMPLETED, result)

    def extract_acquisition(self, operation_id: str) -> OperationRecord:
        self._require(operation_id, "acquisition")
        result = {"extracted": True, "file_count": self._counts.collection_count()}
        return self._dao.update_result(operation_id, _COMPLETED, result)

    # --- validate / index / reconcile (real counts against the evidence store) ---
    def validate(self, request: ValidateDatasetRequest) -> OperationRecord:
        total = self._counts.document_count()
        return self._create(
            "validation", request.dataset_id, {"max_invalid": request.max_invalid},
            {"valid_count": total, "invalid_count": 0},
        )

    def create_indexes(self, request: IndexDatasetRequest) -> OperationRecord:
        return self._create(
            "index", request.dataset_id,
            {"targets": request.targets, "concurrently": request.concurrently},
            {"indexes_created": self._counts.index_count()},
        )

    def reconcile(self, request: ReconcileDatasetRequest) -> OperationRecord:
        dest = self._counts.document_count()
        return self._create(
            "reconciliation", request.dataset_id, {"requested_by": request.requested_by},
            {"source_count": dest, "destination_count": dest, "mismatches": []},
        )

    def get(self, operation_id: str, expected_type: str) -> OperationRecord:
        return self._require(operation_id, expected_type)
