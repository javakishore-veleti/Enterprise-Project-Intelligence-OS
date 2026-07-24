"""Unit tests for the tracker-sync service (fakes; no DB/Airflow)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingestion_api.common.exceptions import NotFoundError
from ingestion_api.dtos.requests import (
    RecordSyncBatchRequest,
    RepositorySyncRequest,
    UpdateSyncRunStatusRequest,
)
from ingestion_api.dtos.responses import SyncBatchInfo, SyncProjectProgress
from ingestion_api.services.tracker_sync import DefaultTrackerSyncService, build_sync_run_id

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


class FakeTrackingDao:
    def __init__(self, watermark=None):
        self.runs = {}
        self.batches = {}          # (run, project) -> set(batch_no)
        self.finalized = []
        self._watermark = watermark

    def insert_run(self, sync_run_id, repo_id, org_id, root_org_id, provider, since, requested_by):
        self.runs[sync_run_id] = {
            "sync_run_id": sync_run_id, "repo_id": repo_id, "org_id": org_id,
            "root_org_id": root_org_id, "provider": provider, "since": since,
            "status": "RUNNING", "projects_intended": [], "projects_considered": 0,
            "projects_total": 0, "issues_total": 0, "requested_by": requested_by,
            "message": None, "started_at": _NOW, "completed_at": None, "updated_at": _NOW}

    def get_run(self, sync_run_id):
        return self.runs.get(sync_run_id)

    def latest_run_for_repo(self, repo_id):
        runs = [r for r in self.runs.values() if r["repo_id"] == repo_id]
        return runs[-1] if runs else None

    def last_completed_watermark(self, repo_id):
        return self._watermark

    def set_run_projects(self, sync_run_id, projects_intended, projects_considered):
        self.runs[sync_run_id]["projects_intended"] = list(projects_intended)
        self.runs[sync_run_id]["projects_considered"] = projects_considered

    def upsert_project_plan(self, sync_run_id, project_key, issues_intended, batches_total):
        self.runs[sync_run_id].setdefault("_plans", {})[project_key] = (issues_intended, batches_total)

    def committed_batch_numbers(self, sync_run_id, project_key):
        return self.batches.get((sync_run_id, project_key), set())

    def commit_batch(self, sync_run_id, project_key, batch_no, source_offset, record_count):
        self.batches.setdefault((sync_run_id, project_key), set()).add(batch_no)

    def finalize_run(self, sync_run_id, status, message):
        run = self.runs.get(sync_run_id)
        if run is None:
            return None
        run["status"] = "COMPLETED" if status != "FAILED" else "FAILED"
        run["message"] = message
        self.finalized.append((sync_run_id, status))
        return run

    def project_progress(self, sync_run_id):
        return [SyncProjectProgress(project_key="Sakai", status="COMPLETED")]

    def recent_batches(self, sync_run_id, limit):
        return [SyncBatchInfo(project_key="Sakai", batch_no=0, source_offset=0,
                              record_count=3, status="COMMITTED", attempts=1, updated_at=_NOW)]


class FakeGateway:
    def __init__(self, fail=False):
        self.calls = []
        self._fail = fail

    def trigger_sync(self, sync_run_id, conf):
        if self._fail:
            raise RuntimeError("airflow down")
        self.calls.append((sync_run_id, conf))
        return f"dag:{sync_run_id}"


def _req(**kw):
    base = dict(org_id="org-1", root_org_id="root-1", provider="fake",
                connection_config={"fake_repos": ["Sakai"]})
    base.update(kw)
    return RepositorySyncRequest(**base)


def test_sync_run_id_format():
    rid = build_sync_run_id("repo-1234-5678", now=_NOW)
    assert rid.startswith("sync__repo1234__")
    assert rid.endswith("20260701000000000000")


def test_start_triggers_dag_with_run_id_as_dag_run_id():
    dao, gw = FakeTrackingDao(), FakeGateway()
    svc = DefaultTrackerSyncService(dao, gw)
    handle = svc.start("repo-123", _req())
    # The generated id is inserted AND passed to the gateway as the dag_run_id.
    assert handle.sync_run_id in dao.runs
    assert gw.calls[0][0] == handle.sync_run_id            # dag_run_id == sync_run_id
    assert gw.calls[0][1]["sync_run_id"] == handle.sync_run_id  # ...and echoed in conf
    assert gw.calls[0][1]["repo_id"] == "repo-123"
    assert handle.status == "RUNNING" and handle.dag_run == f"dag:{handle.sync_run_id}"


def test_since_resolution_full_explicit_and_watermark():
    wm = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # full -> None (ignores watermark)
    dao = FakeTrackingDao(watermark=wm)
    h = DefaultTrackerSyncService(dao, FakeGateway()).start("r", _req(full=True))
    assert dao.runs[h.sync_run_id]["since"] is None
    # explicit since -> that value
    dao = FakeTrackingDao(watermark=wm)
    explicit = datetime(2026, 5, 1, tzinfo=timezone.utc)
    h = DefaultTrackerSyncService(dao, FakeGateway()).start("r", _req(since=explicit))
    assert dao.runs[h.sync_run_id]["since"] == explicit
    # neither -> last completed run's watermark (end-of-day delta)
    dao = FakeTrackingDao(watermark=wm)
    h = DefaultTrackerSyncService(dao, FakeGateway()).start("r", _req())
    assert dao.runs[h.sync_run_id]["since"] == wm


def test_start_marks_failed_when_trigger_fails():
    dao, gw = FakeTrackingDao(), FakeGateway(fail=True)
    with pytest.raises(RuntimeError):
        DefaultTrackerSyncService(dao, gw).start("repo-123", _req())
    assert dao.finalized and dao.finalized[0][1] == "FAILED"


def test_record_batch_and_committed_batches():
    dao, gw = FakeTrackingDao(), FakeGateway()
    svc = DefaultTrackerSyncService(dao, gw)
    h = svc.start("repo-123", _req())
    svc.record_batch(h.sync_run_id, RecordSyncBatchRequest(
        project_key="Sakai", batch_no=0, source_offset=0, record_count=3))
    assert svc.committed_batches(h.sync_run_id, "Sakai") == [0]


def test_progress_not_started_and_by_run():
    dao, gw = FakeTrackingDao(), FakeGateway()
    svc = DefaultTrackerSyncService(dao, gw)
    assert svc.progress("unknown-repo").status == "NOT_STARTED"
    h = svc.start("repo-123", _req())
    prog = svc.progress_by_run(h.sync_run_id)
    assert prog.sync_run_id == h.sync_run_id
    assert prog.projects and prog.projects[0].project_key == "Sakai"
    assert prog.recent_batches and prog.recent_batches[0].batch_no == 0


def test_unknown_run_raises():
    svc = DefaultTrackerSyncService(FakeTrackingDao(), FakeGateway())
    with pytest.raises(NotFoundError):
        svc.progress_by_run("missing")
    with pytest.raises(NotFoundError):
        svc.finalize_run("missing", UpdateSyncRunStatusRequest(status="COMPLETED"))
