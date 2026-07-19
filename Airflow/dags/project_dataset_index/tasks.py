"""Pure, importable task callables for the project dataset indexing DAG.

These functions contain the operational logic and are deliberately kept free of
Airflow imports so they can be unit-tested in isolation with a *fake* HTTP
client (no network, no scheduler, no live Ingestion-API).

The contract for the injected ``http`` client mirrors the ``requests`` module:
it must expose ``post(url, json=..., timeout=...)`` and ``get(url, timeout=...)``
returning a response object with ``raise_for_status()`` and ``json()``.

Airflow owns *operational* work only: these callables trigger and monitor index
creation through the Ingestion-API FastAPI boundary. They never touch a database
directly (the middleware issues the actual DDL) and contain no agent/LLM logic.

Endpoint status: the Ingestion-API currently implements only
``POST /api/v1/ingestion/runs`` and ``GET /api/v1/ingestion/runs/{run_id}``.
The indexing endpoints modelled below are the *intended* REST contract and are
**NOT YET implemented** in the middleware — marked PENDING in-line.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Protocol

TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
NON_TERMINAL_STATUSES = frozenset({"PENDING", "RUNNING"})

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 30

# PENDING endpoints — intended Ingestion-API indexing contract (not yet built).
INDEXES_PATH = "/api/v1/ingestion/indexes"


class HttpClient(Protocol):
    """Minimal HTTP surface used by the task callables (satisfied by ``requests``)."""

    def post(self, url: str, json: Dict[str, Any], timeout: int) -> Any:  # noqa: A002
        ...

    def get(self, url: str, timeout: int) -> Any:
        ...


def get_base_url() -> str:
    """Resolve the Ingestion-API base URL from the environment."""
    return os.environ.get("INGESTION_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def build_index_request(
    dataset_id: str,
    targets: List[str],
    requested_by: str,
    concurrently: bool = True,
) -> Dict[str, Any]:
    """Assemble and validate the index-creation request (a pure shaping step).

    ``targets`` names the collections/tables to index. ``concurrently`` asks the
    middleware to build indexes without long write locks. Raises ``ValueError``
    on invalid inputs so a misconfigured trigger fails fast.
    """
    if not dataset_id:
        raise ValueError("dataset_id is required")
    if not targets:
        raise ValueError("targets must be a non-empty list")
    if not requested_by:
        raise ValueError("requested_by is required")

    return {
        "dataset_id": dataset_id,
        "targets": list(targets),
        "requested_by": requested_by,
        "concurrently": bool(concurrently),
    }


def start_indexing(
    base_url: str,
    http: HttpClient,
    request: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """POST an index-creation job and return ``{index_job_id, status}``.

    PENDING: ``POST /api/v1/ingestion/indexes`` not yet implemented.
    Raises ``RuntimeError`` if the response lacks an ``index_job_id``.
    """
    url = f"{base_url.rstrip('/')}{INDEXES_PATH}"
    response = http.post(url, json=request, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    index_job_id = payload.get("index_job_id")
    if not index_job_id:
        raise RuntimeError(
            f"Ingestion-API did not return an index_job_id: {payload!r}"
        )
    return {"index_job_id": index_job_id, "status": payload.get("status", "PENDING")}


def get_index_status(
    base_url: str,
    http: HttpClient,
    index_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """GET a single indexing resource and return its JSON payload.

    PENDING: ``GET /api/v1/ingestion/indexes/{id}`` not yet implemented.
    """
    url = f"{base_url.rstrip('/')}{INDEXES_PATH}/{index_job_id}"
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def poll_indexing(
    base_url: str,
    http: HttpClient,
    index_job_id: str,
    max_polls: int = 120,
    poll_interval_seconds: float = 20.0,
    timeout: int = DEFAULT_TIMEOUT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Poll the index job until it reaches a terminal status.

    Returns the final payload. Raises ``TimeoutError`` if not terminal within
    ``max_polls`` attempts and ``RuntimeError`` on an unrecognized status.
    """
    if max_polls <= 0:
        raise ValueError("max_polls must be a positive integer")

    last_payload: Optional[Dict[str, Any]] = None
    for attempt in range(max_polls):
        payload = get_index_status(base_url, http, index_job_id, timeout=timeout)
        last_payload = payload
        status = payload.get("status")

        if status in TERMINAL_STATUSES:
            return payload
        if status not in NON_TERMINAL_STATUSES:
            raise RuntimeError(
                f"Unrecognized indexing status {status!r} for {index_job_id}"
            )

        if attempt < max_polls - 1:
            sleep_fn(poll_interval_seconds)

    raise TimeoutError(
        f"Index job {index_job_id} did not reach a terminal status within "
        f"{max_polls} polls (last status: "
        f"{last_payload.get('status') if last_payload else 'unknown'})"
    )


def finalize(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Interpret the terminal index payload and fail the DAG on a bad outcome.

    Returns a compact summary when the job COMPLETED; raises ``RuntimeError``
    otherwise so the Airflow task is marked failed.
    """
    status = payload.get("status")
    index_job_id = payload.get("index_job_id")

    if status == "COMPLETED":
        return {
            "index_job_id": index_job_id,
            "status": status,
            "indexes_created": payload.get("indexes_created"),
            "ok": True,
        }

    raise RuntimeError(
        f"Index job {index_job_id} finished with non-success status {status!r}"
    )
