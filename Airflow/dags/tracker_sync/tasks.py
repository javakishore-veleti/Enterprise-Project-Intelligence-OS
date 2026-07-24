"""Pure task callables for the ``tracker_repository_sync`` DAG.

Airflow-free (unit-testable with fake HTTP clients / fake staging DBs). They:
- build the connector from the repo's ``provider`` (``fake`` -> FakeConnector over
  the ``jira_repos`` staging DB; ``jira``/``azure_devops`` are stubs);
- drive the batched, resumable, org-stamped sync via ``sync_engine``;
- report the two-level tracking log (run / project / batch) through the GOVERNED
  Ingestion-API boundary — the DAG never writes Postgres directly.

The Ingestion-API generates ``sync_run_id`` and passes it as the Airflow
``dag_run_id``, so ``dag_run.run_id == sync_run_id`` and every callback below keys
off that one id.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

INGESTION_DEFAULT_BASE_URL = "http://localhost:8001"
ORG_API_DEFAULT_BASE_URL = "http://localhost:8005"
DEFAULT_TIMEOUT = 60


class HttpClient(Protocol):
    def get(self, url: str, timeout: int = ...) -> Any: ...
    def post(self, url: str, json: Dict[str, Any], timeout: int = ...) -> Any: ...
    def put(self, url: str, json: Dict[str, Any], timeout: int = ...) -> Any: ...


# --- config / env ------------------------------------------------------------ #
def get_ingestion_base_url() -> str:
    return (os.environ.get("INGESTION_API_BASE_URL") or INGESTION_DEFAULT_BASE_URL).rstrip("/")


def get_org_api_base_url() -> str:
    return (os.environ.get("ORG_MANAGEMENT_API_BASE_URL") or ORG_API_DEFAULT_BASE_URL).rstrip("/")


def get_mongo_uri() -> str:
    return os.environ.get("MONGO_URI") or "mongodb://localhost:27017/epi_os"


def get_staging_db_name() -> str:
    return os.environ.get("TRACKER_STAGING_DB", "jira_repos")


def parse_since(value: Any) -> Optional[datetime]:
    """Parse an ISO ``since`` value from conf (``None``/empty -> full sync)."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    v = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


# --- governed tracking-log callbacks (Ingestion-API) ------------------------- #
def record_run_projects(base_url: str, http: HttpClient, sync_run_id: str, *,
                        projects_intended: List[str], projects_considered: int) -> None:
    """Set the run's intended/considered project lists (posted by the ``start`` task)."""
    resp = http.post(
        f"{base_url}/api/v1/ingestion/sync-runs/{sync_run_id}/projects",
        json={"projects_intended": projects_intended, "projects_considered": projects_considered},
        timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()


def plan_project(base_url: str, http: HttpClient, sync_run_id: str, project_key: str, *,
                 issues_intended: int, batches_total: int) -> None:
    """Upsert a project row IN_PROGRESS with its planned totals (posted by ``plan``)."""
    resp = http.post(
        f"{base_url}/api/v1/ingestion/sync-runs/{sync_run_id}/projects/{project_key}/plan",
        json={"issues_intended": issues_intended, "batches_total": batches_total},
        timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()


def committed_batches(base_url: str, http: HttpClient, sync_run_id: str, project_key: str) -> set:
    """Batch numbers already committed for (run, project) — the DAG skips these to resume."""
    resp = http.get(
        f"{base_url}/api/v1/ingestion/sync-runs/{sync_run_id}/projects/{project_key}/committed-batches",
        timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return set(resp.json().get("batch_numbers", []))


def record_batch(base_url: str, http: HttpClient, sync_run_id: str, project_key: str, *,
                 batch_no: int, source_offset: int, record_count: int) -> Dict[str, Any]:
    """Commit a batch checkpoint + atomically bump the project's counters.

    The Ingestion-API does the atomic ``batches_done += 1`` / ``issues_imported +=``
    increment and flips the project to COMPLETED when all batches are in — so
    concurrent batch completions can never lose an update. Returns the server's
    view of the project row (batches_done/status) for logging.
    """
    resp = http.post(
        f"{base_url}/api/v1/ingestion/sync-runs/{sync_run_id}/batches",
        json={"project_key": project_key, "batch_no": batch_no,
              "source_offset": source_offset, "record_count": record_count},
        timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def finalize_run(base_url: str, http: HttpClient, sync_run_id: str, status: str,
                 message: str = "") -> None:
    """Finalize the run (COMPLETED/FAILED); the server derives project rollups."""
    resp = http.put(
        f"{base_url}/api/v1/ingestion/sync-runs/{sync_run_id}/status",
        json={"status": status, "message": message}, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()


# --- connector / staging wiring ---------------------------------------------- #
def open_staging_db():
    """Open the ``jira_repos`` staging DB the FakeConnector replays (real pymongo)."""
    from pymongo import MongoClient  # local import: keep tasks importable without pymongo
    client = MongoClient(get_mongo_uri())
    return client, client[get_staging_db_name()]


def build_connector(provider: str, staging_db: Any):
    from tracker_sync.connectors import build_connector as _build
    return _build(provider, staging_db)


def build_batch_specs(project_key: str, total: int, batch_size: int,
                      already: set) -> List[Dict[str, Any]]:
    """Plan a project's batch windows, skipping already-committed batch numbers."""
    from tracker_sync.sync_engine import plan_batches
    specs: List[Dict[str, Any]] = []
    for window in plan_batches(total, batch_size):
        if window["batch_no"] in already:
            continue
        specs.append(dict(window))
    return specs
