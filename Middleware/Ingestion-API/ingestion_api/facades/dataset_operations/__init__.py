"""Use case: dataset operational sub-operations (acquire/validate/index/reconcile).

Maps internal OperationRecords to the type-specific response shapes the Airflow
DAGs expect (acquisition_id / validation_id / index_job_id / reconciliation_id).
"""
from __future__ import annotations

from ingestion_api.dtos.common import OperationRecord
from ingestion_api.dtos.requests import (
    AcquireDatasetRequest,
    IndexDatasetRequest,
    ReconcileDatasetRequest,
    ValidateDatasetRequest,
    VerifyAcquisitionRequest,
)
from ingestion_api.dtos.responses import (
    AcquisitionExtractResponse,
    AcquisitionResponse,
    AcquisitionVerifyResponse,
    IndexResponse,
    ReconciliationResponse,
    ValidationResponse,
)
from ingestion_api.interfaces.services import OperationsService


def _acquisition(rec: OperationRecord) -> AcquisitionResponse:
    return AcquisitionResponse(acquisition_id=rec.operation_id, dataset_id=rec.dataset_id, status=rec.status)


class DatasetOperationsFacade:
    def __init__(self, service: OperationsService) -> None:
        self._service = service

    # acquisition
    def acquire(self, request: AcquireDatasetRequest) -> AcquisitionResponse:
        return _acquisition(self._service.acquire(request))

    def get_acquisition(self, operation_id: str) -> AcquisitionResponse:
        return _acquisition(self._service.get(operation_id, "acquisition"))

    def verify_acquisition(self, operation_id: str, request: VerifyAcquisitionRequest) -> AcquisitionVerifyResponse:
        rec = self._service.verify_acquisition(operation_id, request.expected_sha256)
        return AcquisitionVerifyResponse(
            acquisition_id=rec.operation_id, status=rec.status,
            verified=bool(rec.result.get("verified")), actual_sha256=rec.result.get("actual_sha256", ""),
        )

    def extract_acquisition(self, operation_id: str) -> AcquisitionExtractResponse:
        rec = self._service.extract_acquisition(operation_id)
        return AcquisitionExtractResponse(
            acquisition_id=rec.operation_id, status=rec.status,
            extracted=bool(rec.result.get("extracted")), file_count=int(rec.result.get("file_count", 0)),
        )

    # validation
    def validate(self, request: ValidateDatasetRequest) -> ValidationResponse:
        return self._to_validation(self._service.validate(request))

    def get_validation(self, operation_id: str) -> ValidationResponse:
        return self._to_validation(self._service.get(operation_id, "validation"))

    @staticmethod
    def _to_validation(rec: OperationRecord) -> ValidationResponse:
        return ValidationResponse(
            validation_id=rec.operation_id, dataset_id=rec.dataset_id, status=rec.status,
            valid_count=int(rec.result.get("valid_count", 0)),
            invalid_count=int(rec.result.get("invalid_count", 0)),
        )

    # index
    def create_indexes(self, request: IndexDatasetRequest) -> IndexResponse:
        return self._to_index(self._service.create_indexes(request))

    def get_index(self, operation_id: str) -> IndexResponse:
        return self._to_index(self._service.get(operation_id, "index"))

    @staticmethod
    def _to_index(rec: OperationRecord) -> IndexResponse:
        return IndexResponse(
            index_job_id=rec.operation_id, dataset_id=rec.dataset_id, status=rec.status,
            indexes_created=int(rec.result.get("indexes_created", 0)),
        )

    # reconciliation
    def reconcile(self, request: ReconcileDatasetRequest) -> ReconciliationResponse:
        return self._to_reconciliation(self._service.reconcile(request))

    def get_reconciliation(self, operation_id: str) -> ReconciliationResponse:
        return self._to_reconciliation(self._service.get(operation_id, "reconciliation"))

    @staticmethod
    def _to_reconciliation(rec: OperationRecord) -> ReconciliationResponse:
        return ReconciliationResponse(
            reconciliation_id=rec.operation_id, dataset_id=rec.dataset_id, status=rec.status,
            source_count=int(rec.result.get("source_count", 0)),
            destination_count=int(rec.result.get("destination_count", 0)),
            mismatches=list(rec.result.get("mismatches", [])),
        )
