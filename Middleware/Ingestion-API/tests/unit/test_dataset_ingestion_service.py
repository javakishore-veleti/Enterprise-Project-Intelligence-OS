"""Unit tests for the dataset batch-ingestion service against fakes."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingestion_api.common.exceptions import ConflictError, DependencyUnavailableError
from ingestion_api.dtos.common import DatasetState, IngestionStatus
from ingestion_api.dtos.requests import (
    ReportBatchProgressRequest,
    StartDatasetIngestionRequest,
    UpdateRunStatusRequest,
)
from ingestion_api.dtos.responses import DatasetStatusResponse, IngestionRunResponse
from ingestion_api.interfaces.daos import (
    DatasetIngestionGateway,
    DatasetsDao,
    IngestionProgressDao,
    IngestionTrackingDao,
    MetricsComputeGateway,
)
from ingestion_api.services.dataset_ingestion import DefaultDatasetIngestionService

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


class FakeDatasets(DatasetsDao):
    def __init__(self, state):
        self.state = state

    def get(self, dataset_id):
        return DatasetStatusResponse(
            dataset_id=dataset_id, title="T", state=self.state, file_name="d.zip",
            source_url="http://x", expected_md5="abc", size_bytes=1, downloaded_bytes=0,
            message="", updated_at=_NOW)

    def update_status(self, *a, **k):
        return None


class FakeTracking(IngestionTrackingDao):
    def __init__(self):
        self.rows = {}

    def insert_run(self, run):
        self.rows[run.run_id] = run
        return run

    def get_run(self, run_id):
        return self.rows.get(run_id)

    def update_status(self, run_id, status):
        r = self.rows[run_id].model_copy(update={"status": status})
        self.rows[run_id] = r
        return r

    def latest_run_for_dataset(self, dataset_id):
        runs = [r for r in self.rows.values() if r.dataset_id == dataset_id]
        return runs[-1] if runs else None


class FakeProgress(IngestionProgressDao):
    def __init__(self, entities=None, log=None):
        self.batches = []
        self._entities = entities or []
        self._log = log or []

    def record_batch(self, run_id, entity, batch_no, source_offset, record_count,
                     records_done, records_total, level, message):
        self.batches.append((run_id, entity, batch_no))

    def committed_batch_numbers(self, run_id, entity):
        return {b[2] for b in self.batches if b[0] == run_id and b[1] == entity}

    def entity_progress(self, run_id):
        return self._entities

    def recent_log(self, run_id, limit):
        return self._log[:limit]


class FakeGateway(DatasetIngestionGateway):
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def trigger_ingest(self, dataset_id, run_id, repos=None):
        self.calls.append((dataset_id, run_id, repos))
        if self.fail:
            raise DependencyUnavailableError("airflow down")
        return "run-xyz"


def _svc(state=DatasetState.DOWNLOADED.value, gateway=None, progress=None):
    return DefaultDatasetIngestionService(
        FakeDatasets(state), FakeTracking(), progress or FakeProgress(), gateway or FakeGateway())


def test_start_requires_downloaded_dataset() -> None:
    with pytest.raises(ConflictError):
        _svc(state=DatasetState.NOT_DOWNLOADED.value).start("public-jira", StartDatasetIngestionRequest())


def test_start_creates_run_and_triggers_dag() -> None:
    gw = FakeGateway()
    svc = _svc(gateway=gw)
    result = svc.start("public-jira", StartDatasetIngestionRequest())
    assert result.dataset_id == "public-jira"
    assert result.run_id is not None
    assert len(gw.calls) == 1 and gw.calls[0][0] == "public-jira"


def test_start_marks_run_failed_when_airflow_down() -> None:
    gw = FakeGateway(fail=True)
    tracking = FakeTracking()
    svc = DefaultDatasetIngestionService(
        FakeDatasets(DatasetState.DOWNLOADED.value), tracking, FakeProgress(), gw)
    with pytest.raises(DependencyUnavailableError):
        svc.start("public-jira", StartDatasetIngestionRequest())
    assert list(tracking.rows.values())[0].status is IngestionStatus.FAILED


def test_progress_not_started_when_no_run() -> None:
    result = _svc().progress("never-run")
    assert result.status == "NOT_STARTED" and result.run_id is None


def test_report_batch_flips_pending_to_running() -> None:
    tracking = FakeTracking()
    progress = FakeProgress()
    svc = DefaultDatasetIngestionService(
        FakeDatasets(DatasetState.DOWNLOADED.value), tracking, progress, FakeGateway())
    started = svc.start("public-jira", StartDatasetIngestionRequest())
    svc.report_batch(started.run_id, ReportBatchProgressRequest(
        entity="issues", batch_no=0, record_count=100, records_done=100, records_total=500))
    assert tracking.rows[started.run_id].status is IngestionStatus.RUNNING
    assert progress.batches[0][1] == "issues"


def test_progress_aggregates_entities() -> None:
    tracking = FakeTracking()
    progress = FakeProgress(
        entities=[("issues", 300, 500), ("projects", 4, 4)],
        log=[("INFO", "issues", "batch 3", 300, 500, _NOW)])
    svc = DefaultDatasetIngestionService(
        FakeDatasets(DatasetState.DOWNLOADED.value), tracking, progress, FakeGateway())
    started = svc.start("public-jira", StartDatasetIngestionRequest())
    result = svc.progress("public-jira")
    assert result.records_done == 304 and result.records_total == 504
    assert {e.entity for e in result.entities} == {"issues", "projects"}
    projects = next(e for e in result.entities if e.entity == "projects")
    assert projects.status == "COMPLETED"  # 4/4
    assert len(result.recent_log) == 1


class FakeMetricsGateway(MetricsComputeGateway):
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def trigger_compute(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("airflow down")
        return "metrics-run-1"


def _svc_with_metrics(metrics, auto=True):
    tracking = FakeTracking()
    svc = DefaultDatasetIngestionService(
        FakeDatasets(DatasetState.DOWNLOADED.value), tracking, FakeProgress(), FakeGateway(),
        metrics_gateway=metrics, auto_compute_metrics=auto)
    started = svc.start("public-jira", StartDatasetIngestionRequest())
    return svc, started.run_id


def test_finalize_run_sets_status() -> None:
    tracking = FakeTracking()
    svc = DefaultDatasetIngestionService(
        FakeDatasets(DatasetState.DOWNLOADED.value), tracking, FakeProgress(), FakeGateway())
    started = svc.start("public-jira", StartDatasetIngestionRequest())
    run = svc.finalize_run(started.run_id, UpdateRunStatusRequest(status="COMPLETED"))
    assert run.status is IngestionStatus.COMPLETED


def test_completed_run_auto_triggers_metrics() -> None:
    metrics = FakeMetricsGateway()
    svc, run_id = _svc_with_metrics(metrics)
    svc.finalize_run(run_id, UpdateRunStatusRequest(status="COMPLETED"))
    assert metrics.calls == 1


def test_failed_run_does_not_trigger_metrics() -> None:
    metrics = FakeMetricsGateway()
    svc, run_id = _svc_with_metrics(metrics)
    svc.finalize_run(run_id, UpdateRunStatusRequest(status="FAILED"))
    assert metrics.calls == 0


def test_metrics_trigger_failure_does_not_fail_finalize() -> None:
    metrics = FakeMetricsGateway(fail=True)
    svc, run_id = _svc_with_metrics(metrics)
    run = svc.finalize_run(run_id, UpdateRunStatusRequest(status="COMPLETED"))
    assert run.status is IngestionStatus.COMPLETED  # best-effort trigger


