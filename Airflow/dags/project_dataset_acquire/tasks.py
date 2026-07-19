"""Pure, importable task callables for the real dataset-acquisition DAG.

Airflow owns operational work: this DAG downloads the configured dataset archive
(the ~5.8 GB public Jira dataset from Zenodo), verifies its md5, and reports
progress to the Ingestion-API dataset resource. The callables are free of Airflow
imports so they can be unit-tested with a *fake* HTTP client + a temp directory
(no network, no scheduler, no live API, no multi-GB download).

Injected ``http`` client mirrors ``requests``:
- ``get(url, timeout=..., stream=...)`` -> response with ``raise_for_status()``,
  ``json()``, and (when streaming) ``iter_content(chunk_size)``.
- ``put(url, json=..., timeout=...)`` -> response with ``raise_for_status()``/``json()``.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Callable, Dict, Optional, Protocol

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 60
DEFAULT_DATA_DIR = "/opt/airflow/data"
DATASETS_PATH = "/api/v1/ingestion/datasets"
DOWNLOAD_CHUNK = 8 * 1024 * 1024  # 8 MiB


class HttpClient(Protocol):
    def get(self, url: str, timeout: int = ..., stream: bool = ...) -> Any: ...
    def put(self, url: str, json: Dict[str, Any], timeout: int = ...) -> Any: ...


def get_base_url() -> str:
    """Resolve the Ingestion-API base URL from the environment (never fails)."""
    return (os.environ.get("INGESTION_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def get_data_dir() -> str:
    return os.environ.get("DATASET_DATA_DIR") or DEFAULT_DATA_DIR


def fetch_dataset(base_url: str, http: HttpClient, dataset_id: str) -> Dict[str, Any]:
    """GET the dataset's status/metadata (source_url, expected_md5, file_name)."""
    resp = http.get(f"{base_url}{DATASETS_PATH}/{dataset_id}", timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def update_status(
    base_url: str,
    http: HttpClient,
    dataset_id: str,
    state: str,
    *,
    downloaded_bytes: Optional[int] = None,
    downloaded_path: Optional[str] = None,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """PUT a state update to the Ingestion-API dataset resource."""
    body: Dict[str, Any] = {"state": state}
    if downloaded_bytes is not None:
        body["downloaded_bytes"] = downloaded_bytes
    if downloaded_path is not None:
        body["downloaded_path"] = downloaded_path
    if message is not None:
        body["message"] = message
    resp = http.put(f"{base_url}{DATASETS_PATH}/{dataset_id}/status", json=body, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _md5_of_file(path: str, chunk: int = DOWNLOAD_CHUNK) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def download_dataset(
    source_url: str,
    dest_path: str,
    http: HttpClient,
    expected_md5: Optional[str] = None,
    chunk_size: int = DOWNLOAD_CHUNK,
    on_progress: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """Stream-download ``source_url`` to ``dest_path``; return path/bytes/md5.

    Idempotent: if the file already exists and its md5 matches ``expected_md5``,
    the download is skipped ("already downloaded"). Streams to a ``.part`` file
    and atomically renames on success, so a partial file is never mistaken for a
    complete one.
    """
    if expected_md5 and os.path.exists(dest_path) and _md5_of_file(dest_path) == expected_md5:
        return {"path": dest_path, "bytes": os.path.getsize(dest_path), "md5": expected_md5, "skipped": True}

    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    resp = http.get(source_url, timeout=DEFAULT_TIMEOUT, stream=True)
    resp.raise_for_status()

    digest = hashlib.md5()
    total = 0
    tmp_path = dest_path + ".part"
    with open(tmp_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size):
            if not chunk:
                continue
            f.write(chunk)
            digest.update(chunk)
            total += len(chunk)
            if on_progress is not None:
                on_progress(total)
    os.replace(tmp_path, dest_path)
    return {"path": dest_path, "bytes": total, "md5": digest.hexdigest(), "skipped": False}


def verify_md5(actual: str, expected: Optional[str]) -> None:
    if expected and actual != expected:
        raise ValueError(f"dataset md5 mismatch: expected {expected!r}, got {actual!r}")
