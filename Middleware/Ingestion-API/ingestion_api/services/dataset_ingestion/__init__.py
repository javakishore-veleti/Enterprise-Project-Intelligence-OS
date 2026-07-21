"""Dataset batch-ingestion service.

Creates an ingestion run, triggers the Airflow ``project_dataset_ingest`` DAG,
and aggregates per-batch progress (from ``ingestion_batches`` / ``ingestion_log``)
for the Admin UI. The DAG does the actual batched Mongo writes; run/batch/log
status stays governed here.
"""
from __future__ import annotations

from ingestion_api.common.exceptions import ConflictError, NotFoundError
from ingestion_api.common.logging import get_logger
from ingestion_api.common.utilities import new_id, utc_now
from ingestion_api.dtos.common import DatasetState, IngestionStatus
from ingestion_api.dtos.requests import (
    ReportBatchProgressRequest,
    StartDatasetIngestionRequest,
    UpdateRunStatusRequest,
)
from ingestion_api.dtos.responses import (
    EntityProgress,
    IngestionLogEntry,
    IngestionProgressResponse,
    IngestionRunResponse,
)
from ingestion_api.interfaces.daos import (
    DatasetIngestionGateway,
    DatasetsDao,
    IngestionProgressDao,
    IngestionTrackingDao,
    MetricsComputeGateway,
)
from ingestion_api.interfaces.services import DatasetIngestionService

_logger = get_logger(__name__)
_FINISHED = {IngestionStatus.COMPLETED.value, IngestionStatus.FAILED.value}


class DefaultDatasetIngestionService(DatasetIngestionService):
    def __init__(
        self,
        datasets_dao: DatasetsDao,
        tracking_dao: IngestionTrackingDao,
        progress_dao: IngestionProgressDao,
        ingest_gateway: DatasetIngestionGateway,
        metrics_gateway: MetricsComputeGateway | None = None,
        auto_compute_metrics: bool = False,
    ) -> None:
        self._datasets = datasets_dao
        self._tracking = tracking_dao
        self._progress = progress_dao
        self._airflow = ingest_gateway
        self._metrics = metrics_gateway
        self._auto_compute = auto_compute_metrics

    def start(self, dataset_id: str, request: StartDatasetIngestionRequest) -> IngestionProgressResponse:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"dataset '{dataset_id}' not found")
        if dataset.state != DatasetState.DOWNLOADED.value:
            raise ConflictError(
                f"dataset '{dataset_id}' is '{dataset.state}', not DOWNLOADED — download it first."
            )

        run = self._tracking.insert_run(IngestionRunResponse(
            run_id=new_id(), dataset_id=dataset_id, status=IngestionStatus.PENDING,
            batch_size=request.batch_size, parallelism=request.parallelism,
            requested_by=request.requested_by, created_at=utc_now(), updated_at=utc_now(),
        ))
        try:
            dag_run = self._airflow.trigger_ingest(dataset_id, run.run_id, repos=request.repos)
        except Exception:
            self._tracking.update_status(run.run_id, IngestionStatus.FAILED)
            raise
        _logger.info("ingestion started", extra={"context": {
            "run_id": run.run_id, "dataset_id": dataset_id, "dag_run": dag_run}})
        return self._progress_for_run(run.run_id, dataset_id)

    def progress(self, dataset_id: str) -> IngestionProgressResponse:
        run = self._tracking.latest_run_for_dataset(dataset_id)
        if run is None:
            return IngestionProgressResponse(run_id=None, dataset_id=dataset_id, status="NOT_STARTED")
        return self._progress_for_run(run.run_id, dataset_id)

    def report_batch(self, run_id: str, request: ReportBatchProgressRequest) -> None:
        self._progress.record_batch(
            run_id, request.entity, request.batch_no, request.source_offset,
            request.record_count, request.records_done, request.records_total,
            request.level, request.message,
        )
        # First batch flips a PENDING run to RUNNING.
        run = self._tracking.get_run(run_id)
        if run is not None and run.status is IngestionStatus.PENDING:
            self._tracking.update_status(run_id, IngestionStatus.RUNNING)

    def finalize_run(self, run_id: str, request: UpdateRunStatusRequest) -> IngestionRunResponse:
        run = self._tracking.update_status(run_id, IngestionStatus(request.status))
        if run is None:
            raise NotFoundError(f"ingestion run '{run_id}' not found")
        # Chain the pipeline: a completed ingestion auto-triggers metric computation
        # (best-effort — a metrics-trigger failure must not fail the run finalize).
        if (self._auto_compute and self._metrics is not None
                and run.status is IngestionStatus.COMPLETED):
            try:
                dag_run = self._metrics.trigger_compute()
                _logger.info("metric computation auto-triggered", extra={"context": {
                    "run_id": run_id, "dag_run": dag_run}})
            except Exception as exc:  # pragma: no cover - best effort
                _logger.warning("metric auto-trigger failed", extra={"context": {
                    "run_id": run_id, "error": str(exc)}})
        return run

    def committed_batches(self, run_id: str, entity: str) -> list[int]:
        return sorted(self._progress.committed_batch_numbers(run_id, entity))

    # --- aggregation ---
    def _progress_for_run(self, run_id: str, dataset_id: str) -> IngestionProgressResponse:
        run = self._tracking.get_run(run_id)
        rows = self._progress.entity_progress(run_id)
        run_status = run.status.value if run else "PENDING"
        entities = []
        done_sum = total_sum = 0
        for entity, done, total in rows:
            done_sum += done
            total_sum += total
            e_status = "COMPLETED" if (total > 0 and done >= total) or run_status == "COMPLETED" else run_status
            entities.append(EntityProgress(entity=entity, records_done=done, records_total=total, status=e_status))
        log = [
            IngestionLogEntry(level=r[0], entity=r[1], message=r[2], records_done=r[3],
                              records_total=r[4], created_at=r[5])
            for r in self._progress.recent_log(run_id, 20)
        ]
        finished = run.updated_at if (run and run.status.value in _FINISHED) else None
        return IngestionProgressResponse(
            run_id=run_id, dataset_id=dataset_id, status=run_status,
            started_at=run.created_at if run else None, finished_at=finished,
            records_done=done_sum, records_total=total_sum, entities=entities, recent_log=log,
        )
