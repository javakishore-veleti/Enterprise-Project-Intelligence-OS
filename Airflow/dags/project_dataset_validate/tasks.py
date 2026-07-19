"""Pure, importable task callables for the project dataset validation DAG.

These functions contain the operational logic and are deliberately kept free of
Airflow imports so they can be unit-tested in isolation with a *fake* HTTP
client (no network, no scheduler, no live Ingestion-API).

The contract for the injected ``http`` client mirrors the ``requests`` module:
it must expose ``post(url, json=..., timeout=...)`` and ``get(url, timeout=...)``
returning a response object with ``raise_for_status()`` and ``json()``.

Airflow owns *operational* work only: these callables trigger and monitor record
validation through the Ingestion-API FastAPI boundary. They never touch a
database directly and contain no agent/LLM/reasoning logic.

Endpoint status: the Ingestion-API currently implements only
``POST /api/v1/ingestion/runs`` and ``GET /api/v1/ingestion/runs/{run_id}``.
The validation endpoints modelled below are the *intended* REST contract and are
**NOT YET implemented** in the middleware — marked PENDING in-line.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Optional, Protocol

TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
NON_TERMINAL_STATUSES = frozenset({"PENDING", "RUNNING"})

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 30

# PENDING endpoints — intended Ingestion-API validation contract (not yet built).
VALIDATIONS_PATH = "/api/v1/ingestion/validations"


class HttpClient(Protocol):
    """Minimal HTTP surface used by the task callables (satisfied by ``requests``)."""

    def post(self, url: str, json: Dict[str, Any], timeout: int) -> Any:  # noqa: A002
        ...

    def get(self, url: str, timeout: int) -> Any:
        ...


def get_base_url() -> str:
    """Resolve the Ingestion-API base URL from the environment."""
    return os.environ.get("INGESTION_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def build_validation_request(
    dataset_id: str,
    requested_by: str,
    max_invalid: int = 0,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble and validate the validation-job request (a pure shaping step).

    ``max_invalid`` is the tolerated number of invalid records before the DAG
    fails. Raises ``ValueError`` on invalid inputs so a misconfigured trigger
    fails fast.
    """
    if not dataset_id:
        raise ValueError("dataset_id is required")
    if not requested_by:
        raise ValueError("requested_by is required")
    if max_invalid < 0:
        raise ValueError("max_invalid must be >= 0")

    request: Dict[str, Any] = {
        "dataset_id": dataset_id,
        "requested_by": requested_by,
        "max_invalid": int(max_invalid),
    }
    if run_id:
        request["run_id"] = run_id
    return request


def start_validation(
    base_url: str,
    http: HttpClient,
    request: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """POST a validation job and return ``{validation_id, status}``.

    PENDING: ``POST /api/v1/ingestion/validations`` not yet implemented.
    Raises ``RuntimeError`` if the response lacks a ``validation_id``.
    """
    url = f"{base_url.rstrip('/')}{VALIDATIONS_PATH}"
    response = http.post(url, json=request, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    validation_id = payload.get("validation_id")
    if not validation_id:
        raise RuntimeError(
            f"Ingestion-API did not return a validation_id: {payload!r}"
        )
    return {"validation_id": validation_id, "status": payload.get("status", "PENDING")}


def get_validation_status(
    base_url: str,
    http: HttpClient,
    validation_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """GET a single validation resource and return its JSON payload.

    PENDING: ``GET /api/v1/ingestion/validations/{id}`` not yet implemented.
    """
    url = f"{base_url.rstrip('/')}{VALIDATIONS_PATH}/{validation_id}"
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def poll_validation(
    base_url: str,
    http: HttpClient,
    validation_id: str,
    max_polls: int = 120,
    poll_interval_seconds: float = 15.0,
    timeout: int = DEFAULT_TIMEOUT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Poll the validation job until it reaches a terminal status.

    Returns the final payload. Raises ``TimeoutError`` if not terminal within
    ``max_polls`` attempts and ``RuntimeError`` on an unrecognized status.
    """
    if max_polls <= 0:
        raise ValueError("max_polls must be a positive integer")

    last_payload: Optional[Dict[str, Any]] = None
    for attempt in range(max_polls):
        payload = get_validation_status(base_url, http, validation_id, timeout=timeout)
        last_payload = payload
        status = payload.get("status")

        if status in TERMINAL_STATUSES:
            return payload
        if status not in NON_TERMINAL_STATUSES:
            raise RuntimeError(
                f"Unrecognized validation status {status!r} for {validation_id}"
            )

        if attempt < max_polls - 1:
            sleep_fn(poll_interval_seconds)

    raise TimeoutError(
        f"Validation {validation_id} did not reach a terminal status within "
        f"{max_polls} polls (last status: "
        f"{last_payload.get('status') if last_payload else 'unknown'})"
    )


def evaluate_validation(
    payload: Dict[str, Any],
    max_invalid: int = 0,
) -> Dict[str, Any]:
    """Interpret the terminal validation payload and fail on a bad outcome.

    Fails the DAG when the job did not COMPLETE, or when the number of invalid
    records exceeds ``max_invalid``. Returns a compact summary on success.
    """
    status = payload.get("status")
    validation_id = payload.get("validation_id")

    if status != "COMPLETED":
        raise RuntimeError(
            f"Validation {validation_id} finished with non-success status {status!r}"
        )

    invalid_count = int(payload.get("invalid_count", 0))
    if invalid_count > max_invalid:
        raise RuntimeError(
            f"Validation {validation_id} found {invalid_count} invalid records "
            f"(tolerated {max_invalid})"
        )

    return {
        "validation_id": validation_id,
        "status": status,
        "invalid_count": invalid_count,
        "valid_count": payload.get("valid_count"),
        "ok": True,
    }
