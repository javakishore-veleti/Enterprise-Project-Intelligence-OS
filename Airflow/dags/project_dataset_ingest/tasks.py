"""Pure, importable task callables for the real batch-ingestion DAG.

Airflow owns operational batch work: this DAG extracts the downloaded archive,
discovers per-entity record files, and streams them into MongoDB in bounded,
idempotent batches — committing a durable checkpoint + progress event per batch
so a failed/paused run resumes from the last committed batch. The complete
dataset is never loaded into memory at once.

Design (see CLAUDE.md): evidence writes go straight to Mongo (throughput; the
operational tier), while run/batch/log status is reported through the governed
Ingestion-API boundary. The callables are Airflow-free and unit-testable with a
fake HTTP client, a temp dir, and a fake Mongo collection.

Record files are read as JSON Lines (``.jsonl``/``.ndjson``), one JSON object
per line; the entity name is the file stem. The discover mapping can be adjusted
once the real archive's internal layout is known.
"""
from __future__ import annotations

import json
import os
import zipfile
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Tuple

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 60
DEFAULT_BATCH_SIZE = 1000
RECORD_SUFFIXES = (".jsonl", ".ndjson")


class HttpClient(Protocol):
    def get(self, url: str, timeout: int = ...) -> Any: ...
    def post(self, url: str, json: Dict[str, Any], timeout: int = ...) -> Any: ...
    def put(self, url: str, json: Dict[str, Any], timeout: int = ...) -> Any: ...


def get_base_url() -> str:
    return (os.environ.get("INGESTION_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


# --- Ingestion-API status callbacks (governed boundary) ------------------- #
def fetch_dataset(base_url: str, http: HttpClient, dataset_id: str) -> Dict[str, Any]:
    resp = http.get(f"{base_url}/api/v1/ingestion/datasets/{dataset_id}", timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def report_batch(base_url: str, http: HttpClient, run_id: str, *, entity: str, batch_no: int,
                 source_offset: int, record_count: int, records_done: int, records_total: int,
                 message: str = "", level: str = "INFO") -> None:
    resp = http.post(
        f"{base_url}/api/v1/ingestion/runs/{run_id}/progress",
        json={"entity": entity, "batch_no": batch_no, "source_offset": source_offset,
              "record_count": record_count, "records_done": records_done,
              "records_total": records_total, "message": message, "level": level},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()


def finalize_run(base_url: str, http: HttpClient, run_id: str, status: str, message: str = "") -> None:
    resp = http.put(f"{base_url}/api/v1/ingestion/runs/{run_id}/status",
                    json={"status": status, "message": message}, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()


def committed_batches(base_url: str, http: HttpClient, run_id: str, entity: str) -> set:
    resp = http.get(
        f"{base_url}/api/v1/ingestion/runs/{run_id}/entities/{entity}/committed-batches",
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return set(resp.json().get("batch_numbers", []))


# --- Extraction + discovery ---------------------------------------------- #
def extract_archive(zip_path: str, work_dir: str) -> str:
    """Extract ``zip_path`` into ``work_dir`` (idempotent) and return the dir."""
    os.makedirs(work_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(work_dir)
    return work_dir


def discover_entities(work_dir: str) -> List[Tuple[str, str, int]]:
    """Return [(entity, file_path, record_total)] for each record file found.

    Streams the line count so nothing large is held in memory.
    """
    found: List[Tuple[str, str, int]] = []
    for root, _dirs, files in os.walk(work_dir):
        for name in sorted(files):
            if name.lower().endswith(RECORD_SUFFIXES):
                path = os.path.join(root, name)
                entity = os.path.splitext(name)[0].lower()
                found.append((entity, path, _count_lines(path)))
    return sorted(found)


def _count_lines(path: str) -> int:
    total = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                total += 1
    return total


def iter_batches(path: str, batch_size: int = DEFAULT_BATCH_SIZE) -> Iterator[Tuple[int, int, List[dict]]]:
    """Yield (batch_no, start_line_offset, records) streaming a JSON-lines file."""
    batch: List[dict] = []
    batch_no = 0
    start_offset = 0
    line_no = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line_no += 1
            line = line.strip()
            if not line:
                continue
            batch.append(json.loads(line))
            if len(batch) >= batch_size:
                yield batch_no, start_offset, batch
                batch_no += 1
                start_offset = line_no
                batch = []
    if batch:
        yield batch_no, start_offset, batch


def natural_key(entity: str) -> str:
    """The field used for idempotent upserts, by entity (best-effort default)."""
    return {
        "projects": "project_key", "issues": "issue_key", "issue_links": "link_id",
        "comments": "comment_id", "issue_histories": "history_id",
    }.get(entity, "id")


def upsert_batch(collection: Any, records: List[dict], key_field: str) -> int:
    """Idempotent upsert of a batch into a Mongo collection. Returns count written.

    Records without the key field fall back to insert. ``collection`` mirrors a
    pymongo collection (``update_one(filter, {"$set":...}, upsert=True)``).
    """
    for rec in records:
        if key_field in rec:
            collection.update_one({key_field: rec[key_field]}, {"$set": rec}, upsert=True)
        else:
            collection.insert_one(rec)
    return len(records)
