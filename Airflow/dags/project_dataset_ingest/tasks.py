"""Pure, importable task callables for the project dataset ingestion DAG.

These functions contain the operational logic and are deliberately kept free of
Airflow imports so they can be unit-tested in isolation with a *fake* HTTP
client (no network, no scheduler, no live Ingestion-API).

The contract for the injected ``http`` client mirrors the ``requests`` module:
it must expose ``post(url, json=..., timeout=...)`` and ``get(url, timeout=...)``
returning a response object with ``raise_for_status()`` and ``json()``.

Airflow owns *operational* work only: these callables trigger and monitor
ingestion through the Ingestion-API FastAPI boundary. They never touch a
database directly and contain no agent/LLM/reasoning logic.
"""

from __future__ import annotations

import os
import shutil
import time
from typing import Any, Callable, Dict, Optional, Protocol

# Statuses returned by the Ingestion-API run resource.
TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
NON_TERMINAL_STATUSES = frozenset({"PENDING", "RUNNING", "PAUSED"})

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 30
RUNS_PATH = "/api/v1/ingestion/runs"


class HttpClient(Protocol):
    """Minimal HTTP surface used by the task callables (satisfied by ``requests``)."""

    def post(self, url: str, json: Dict[str, Any], timeout: int) -> Any:  # noqa: A002
        ...

    def get(self, url: str, timeout: int) -> Any:
        ...


def get_base_url() -> str:
    """Resolve the Ingestion-API base URL from the environment.

    Falls back to :data:`DEFAULT_BASE_URL` so DAG parsing never fails on a
    missing variable.
    """
    return os.environ.get("INGESTION_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def read_metadata(
    dataset_id: str,
    batch_size: int,
    parallelism: int,
    requested_by: str,
) -> Dict[str, Any]:
    """Assemble the ingestion request metadata (a pure validation/shaping step).

    Raises ``ValueError`` on obviously invalid inputs so a misconfigured trigger
    fails fast, before any HTTP call is made.
    """
    if not dataset_id:
        raise ValueError("dataset_id is required")
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if parallelism <= 0:
        raise ValueError("parallelism must be a positive integer")
    if not requested_by:
        raise ValueError("requested_by is required")

    return {
        "dataset_id": dataset_id,
        "batch_size": int(batch_size),
        "parallelism": int(parallelism),
        "requested_by": requested_by,
    }


def check_disk_space(
    min_free_bytes: int,
    path: str = "/",
    usage_fn: Callable[[str], Any] = shutil.disk_usage,
) -> Dict[str, Any]:
    """Ensure the worker has enough free disk before requesting ingestion.

    ``usage_fn`` is injectable so tests can supply a fake without touching the
    real filesystem. Raises ``RuntimeError`` when free space is insufficient.
    """
    usage = usage_fn(path)
    free = int(usage.free)
    if free < min_free_bytes:
        raise RuntimeError(
            f"Insufficient disk space at {path!r}: "
            f"{free} bytes free, need at least {min_free_bytes}"
        )
    return {"path": path, "free_bytes": free, "min_free_bytes": int(min_free_bytes)}


def start_ingestion(
    base_url: str,
    http: HttpClient,
    metadata: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """POST an ingestion run to the Ingestion-API and return ``{run_id, status}``.

    Raises ``RuntimeError`` if the response lacks a ``run_id``.
    """
    url = f"{base_url.rstrip('/')}{RUNS_PATH}"
    response = http.post(url, json=metadata, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    run_id = payload.get("run_id")
    if not run_id:
        raise RuntimeError(f"Ingestion-API did not return a run_id: {payload!r}")

    return {"run_id": run_id, "status": payload.get("status", "PENDING")}


def get_run_status(
    base_url: str,
    http: HttpClient,
    run_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """GET a single ingestion run resource and return its JSON payload."""
    url = f"{base_url.rstrip('/')}{RUNS_PATH}/{run_id}"
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def poll_status(
    base_url: str,
    http: HttpClient,
    run_id: str,
    max_polls: int = 120,
    poll_interval_seconds: float = 15.0,
    timeout: int = DEFAULT_TIMEOUT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Poll the run until it reaches a terminal status.

    ``sleep_fn`` is injectable so tests run without real delays. Returns the
    final run payload. Raises ``TimeoutError`` if the run has not reached a
    terminal status within ``max_polls`` attempts, and ``RuntimeError`` on an
    unrecognized status value.
    """
    if max_polls <= 0:
        raise ValueError("max_polls must be a positive integer")

    last_payload: Optional[Dict[str, Any]] = None
    for attempt in range(max_polls):
        payload = get_run_status(base_url, http, run_id, timeout=timeout)
        last_payload = payload
        status = payload.get("status")

        if status in TERMINAL_STATUSES:
            return payload
        if status not in NON_TERMINAL_STATUSES:
            raise RuntimeError(
                f"Unrecognized ingestion run status {status!r} for run {run_id}"
            )

        # Not terminal yet; wait before the next poll (skip after final attempt).
        if attempt < max_polls - 1:
            sleep_fn(poll_interval_seconds)

    raise TimeoutError(
        f"Ingestion run {run_id} did not reach a terminal status within "
        f"{max_polls} polls (last status: "
        f"{last_payload.get('status') if last_payload else 'unknown'})"
    )


def finalize(run_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Interpret the terminal run payload and fail the DAG on a bad outcome.

    Returns a compact summary when the run COMPLETED; raises ``RuntimeError``
    for FAILED/CANCELLED so the Airflow task is marked failed.
    """
    status = run_payload.get("status")
    run_id = run_payload.get("run_id")

    if status == "COMPLETED":
        return {"run_id": run_id, "status": status, "ok": True}

    raise RuntimeError(
        f"Ingestion run {run_id} finished with non-success status {status!r}"
    )
