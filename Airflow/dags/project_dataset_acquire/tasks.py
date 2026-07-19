"""Pure, importable task callables for the project dataset acquisition DAG.

These functions contain the operational logic and are deliberately kept free of
Airflow imports so they can be unit-tested in isolation with a *fake* HTTP
client (no network, no scheduler, no live Ingestion-API).

The contract for the injected ``http`` client mirrors the ``requests`` module:
it must expose ``post(url, json=..., timeout=...)`` and ``get(url, timeout=...)``
returning a response object with ``raise_for_status()`` and ``json()``.

Airflow owns *operational* work only: these callables acquire, verify, and
extract the dataset through the Ingestion-API FastAPI boundary. They never touch
a database directly and contain no agent/LLM/reasoning logic.

Endpoint status (as of this DAG): the Ingestion-API currently implements only
``POST /api/v1/ingestion/runs`` and ``GET /api/v1/ingestion/runs/{run_id}``.
The acquisition/verify/extract endpoints modelled below are the *intended* REST
contract and are **implemented** in the middleware — they are marked
documented in-line. The DAG parses and its callables are fully unit-tested against
a fake client regardless.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Optional, Protocol

# Statuses returned by the Ingestion-API acquisition resource.
TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
NON_TERMINAL_STATUSES = frozenset({"PENDING", "DOWNLOADING", "RUNNING"})

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 30

# Endpoints — the Ingestion-API acquisition contract (now built).
ACQUISITIONS_PATH = "/api/v1/ingestion/acquisitions"


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


def build_acquire_spec(
    dataset_id: str,
    source_url: str,
    expected_sha256: str,
    requested_by: str,
) -> Dict[str, Any]:
    """Assemble and validate the acquisition request (a pure shaping step).

    Raises ``ValueError`` on obviously invalid inputs so a misconfigured trigger
    fails fast, before any HTTP call is made.
    """
    if not dataset_id:
        raise ValueError("dataset_id is required")
    if not source_url:
        raise ValueError("source_url is required")
    if not expected_sha256:
        raise ValueError("expected_sha256 is required")
    if not requested_by:
        raise ValueError("requested_by is required")

    return {
        "dataset_id": dataset_id,
        "source_url": source_url,
        "expected_sha256": expected_sha256,
        "requested_by": requested_by,
    }


def start_acquisition(
    base_url: str,
    http: HttpClient,
    spec: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """POST an acquisition (download) job and return ``{acquisition_id, status}``.

    NOTE: ``POST /api/v1/ingestion/acquisitions`` is implemented in
    the Ingestion-API. Modelled against the intended contract.

    Raises ``RuntimeError`` if the response lacks an ``acquisition_id``.
    """
    url = f"{base_url.rstrip('/')}{ACQUISITIONS_PATH}"
    response = http.post(url, json=spec, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    acquisition_id = payload.get("acquisition_id")
    if not acquisition_id:
        raise RuntimeError(
            f"Ingestion-API did not return an acquisition_id: {payload!r}"
        )

    return {
        "acquisition_id": acquisition_id,
        "status": payload.get("status", "PENDING"),
    }


def get_acquisition_status(
    base_url: str,
    http: HttpClient,
    acquisition_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """GET a single acquisition resource and return its JSON payload.

    NOTE: ``GET /api/v1/ingestion/acquisitions/{id}`` implemented.
    """
    url = f"{base_url.rstrip('/')}{ACQUISITIONS_PATH}/{acquisition_id}"
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def poll_acquisition(
    base_url: str,
    http: HttpClient,
    acquisition_id: str,
    max_polls: int = 240,
    poll_interval_seconds: float = 15.0,
    timeout: int = DEFAULT_TIMEOUT,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Poll the acquisition until it reaches a terminal status.

    ``sleep_fn`` is injectable so tests run without real delays. Returns the
    final payload. Raises ``TimeoutError`` if not terminal within ``max_polls``
    attempts, and ``RuntimeError`` on an unrecognized status value.
    """
    if max_polls <= 0:
        raise ValueError("max_polls must be a positive integer")

    last_payload: Optional[Dict[str, Any]] = None
    for attempt in range(max_polls):
        payload = get_acquisition_status(base_url, http, acquisition_id, timeout=timeout)
        last_payload = payload
        status = payload.get("status")

        if status in TERMINAL_STATUSES:
            return payload
        if status not in NON_TERMINAL_STATUSES:
            raise RuntimeError(
                f"Unrecognized acquisition status {status!r} for {acquisition_id}"
            )

        if attempt < max_polls - 1:
            sleep_fn(poll_interval_seconds)

    raise TimeoutError(
        f"Acquisition {acquisition_id} did not reach a terminal status within "
        f"{max_polls} polls (last status: "
        f"{last_payload.get('status') if last_payload else 'unknown'})"
    )


def verify_checksum(
    base_url: str,
    http: HttpClient,
    acquisition_id: str,
    expected_sha256: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Ask the Ingestion-API to verify the downloaded artifact's checksum.

    NOTE: ``POST /api/v1/ingestion/acquisitions/{id}/verify`` now built.
    Raises ``RuntimeError`` when the checksum does not match.
    """
    url = f"{base_url.rstrip('/')}{ACQUISITIONS_PATH}/{acquisition_id}/verify"
    response = http.post(url, json={"expected_sha256": expected_sha256}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    if not payload.get("verified"):
        raise RuntimeError(
            f"Checksum verification failed for acquisition {acquisition_id}: "
            f"expected {expected_sha256!r}, got {payload.get('actual_sha256')!r}"
        )
    return payload


def extract_dataset(
    base_url: str,
    http: HttpClient,
    acquisition_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Ask the Ingestion-API to extract the verified archive.

    NOTE: ``POST /api/v1/ingestion/acquisitions/{id}/extract`` now built.
    Raises ``RuntimeError`` when extraction did not complete.
    """
    url = f"{base_url.rstrip('/')}{ACQUISITIONS_PATH}/{acquisition_id}/extract"
    response = http.post(url, json={}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    if not payload.get("extracted"):
        raise RuntimeError(
            f"Extraction did not complete for acquisition {acquisition_id}: {payload!r}"
        )
    return payload


def finalize(
    acquisition_id: str,
    extract_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Interpret the extract result and produce a compact success summary."""
    return {
        "acquisition_id": acquisition_id,
        "extracted": True,
        "file_count": extract_payload.get("file_count"),
        "ok": True,
    }
