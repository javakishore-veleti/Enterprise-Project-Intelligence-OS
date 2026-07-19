"""Pure, importable task callables for the project dataset reconciliation DAG.

These functions contain the operational logic and are deliberately kept free of
Airflow imports so they can be unit-tested in isolation with a *fake* HTTP
client (no network, no scheduler, no live Ingestion-API).

The contract for the injected ``http`` client mirrors the ``requests`` module:
it must expose ``post(url, json=..., timeout=...)`` and ``get(url, timeout=...)``
returning a response object with ``raise_for_status()`` and ``json()``.

Airflow owns *operational* work only: these callables trigger and monitor a
source-vs-destination count reconciliation through the Ingestion-API FastAPI
boundary. They never touch a database directly and contain no agent/LLM logic.

Endpoint status: the Ingestion-API currently implements only
``POST /api/v1/ingestion/runs`` and ``GET /api/v1/ingestion/runs/{run_id}``.
The reconciliation endpoints modelled below are the *intended* REST contract and
are **implemented** in the middleware — documented in-line.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Protocol

TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
NON_TERMINAL_STATUSES = frozenset({"PENDING", "RUNNING"})

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 30

# Endpoints — the Ingestion-API reconciliation contract (now built).
RECONCILIATIONS_PATH = "/api/v1/ingestion/reconciliations"


class HttpClient(Protocol):
    """Minimal HTTP surface used by the task callables (satisfied by ``requests``)."""

    def post(self, url: str, json: Dict[str, Any], timeout: int) -> Any:  # noqa: A002
        ...

    def get(self, url: str, timeout: int) -> Any:
        ...


def get_base_url() -> str:
    """Resolve the Ingestion-API base URL from the environment."""
    return os.environ.get("INGESTION_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def build_reconcile_request(
    dataset_id: str,
    requested_by: str,
    entities: Optional[List[str]] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble and validate the reconciliation request (a pure shaping step).

    ``entities`` optionally scopes which record types to reconcile. Raises
    ``ValueError`` on invalid inputs so a misconfigured trigger fails fast.
    """
    if not dataset_id:
        raise ValueError("dataset_id is required")
    if not requested_by:
        raise ValueError("requested_by is required")

    request: Dict[str, Any] = {
        "dataset_id": dataset_id,
        "requested_by": requested_by,
    }
    if entities:
        request["entities"] = list(entities)
    if run_id:
        request["run_id"] = run_id
    return request


def start_reconciliation(
    base_url: str,
    http: HttpClient,
    request: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """POST a reconciliation job and return ``{reconciliation_id, status}``.

    NOTE: ``POST /api/v1/ingestion/reconciliations`` implemented.
    Raises ``RuntimeError`` if the response lacks a ``reconciliation_id``.
    """
    url = f"{base_url.rstrip('/')}{RECONCILIATIONS_PATH}"
    response = http.post(url, json=request, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    reconciliation_id = payload.get("reconciliation_id")
    if not reconciliation_id:
        raise RuntimeError(
            f"Ingestion-API did not return a reconciliation_id: {payload!r}"
        )
    return {
        "reconciliation_id": reconciliation_id,
        "status": payload.get("status", "PENDING"),
    }


def get_reconciliation_status(
    base_url: str,
    http: HttpClient,
    reconciliation_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """GET a single reconciliation resource and return its JSON payload.

    NOTE: ``GET /api/v1/ingestion/reconciliations/{id}`` implemented.
    """
    url = f"{base_url.rstrip('/')}{RECONCILIATIONS_PATH}/{reconciliation_id}"
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def poll_reconciliation(
    base_url: str,
    http: HttpClient,
    reconciliation_id: str,
    max_polls: int = 120,
    poll_interval_seconds: float = 15.0,
    timeout: int = DEFAULT_TIMEOUT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Poll the reconciliation job until it reaches a terminal status.

    Returns the final payload. Raises ``TimeoutError`` if not terminal within
    ``max_polls`` attempts and ``RuntimeError`` on an unrecognized status.
    """
    if max_polls <= 0:
        raise ValueError("max_polls must be a positive integer")

    last_payload: Optional[Dict[str, Any]] = None
    for attempt in range(max_polls):
        payload = get_reconciliation_status(
            base_url, http, reconciliation_id, timeout=timeout
        )
        last_payload = payload
        status = payload.get("status")

        if status in TERMINAL_STATUSES:
            return payload
        if status not in NON_TERMINAL_STATUSES:
            raise RuntimeError(
                f"Unrecognized reconciliation status {status!r} for {reconciliation_id}"
            )

        if attempt < max_polls - 1:
            sleep_fn(poll_interval_seconds)

    raise TimeoutError(
        f"Reconciliation {reconciliation_id} did not reach a terminal status "
        f"within {max_polls} polls (last status: "
        f"{last_payload.get('status') if last_payload else 'unknown'})"
    )


def evaluate_reconciliation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Interpret the terminal reconciliation payload and fail on a mismatch.

    Fails the DAG when the job did not COMPLETE or when the reported
    ``mismatches`` list is non-empty (source and destination counts diverge).
    Returns a compact summary on success.
    """
    status = payload.get("status")
    reconciliation_id = payload.get("reconciliation_id")

    if status != "COMPLETED":
        raise RuntimeError(
            f"Reconciliation {reconciliation_id} finished with non-success "
            f"status {status!r}"
        )

    mismatches = payload.get("mismatches") or []
    if mismatches:
        raise RuntimeError(
            f"Reconciliation {reconciliation_id} found count mismatches: {mismatches!r}"
        )

    return {
        "reconciliation_id": reconciliation_id,
        "status": status,
        "matched": True,
        "source_count": payload.get("source_count"),
        "destination_count": payload.get("destination_count"),
        "ok": True,
    }
