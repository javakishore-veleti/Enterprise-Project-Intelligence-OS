"""Pure task callables for the real batch-ingestion DAG (mongorestore + normalize).

The public Jira dataset ships as a MongoDB dump
(``3. DataDump/mongodump-JiraReposAnon.archive``: ``mongodump --gzip --archive``
of the ``JiraReposAnon`` DB — one collection per Jira repo, each holding standard
Jira REST-v2 issue documents with an embedded ``changelog`` and ``issuelinks``.
Confirmed live (2026-07-21, Mindville restore): status changes live in
``changelog.histories[].items[]`` and links in ``fields.issuelinks[]``; the dump
carries **no** ``fields.comment`` — comments are absent dataset-wide).

So ingestion is: extract the zip -> ``mongorestore`` the archive into a staging
DB -> **normalize** each repo collection's issues into our clean evidence
collections (projects / issues / issue_histories / comments / issue_links), in
bounded, idempotent, checkpointed batches. Metrics + agents read those normalized
collections unchanged. Callables are Airflow-free and unit-testable with fakes.
"""
from __future__ import annotations

import glob
import os
import subprocess
from datetime import datetime
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Tuple

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 60
DEFAULT_BATCH_SIZE = 1000
STAGING_DB = "jira_repos"


class HttpClient(Protocol):
    def get(self, url: str, timeout: int = ...) -> Any: ...
    def post(self, url: str, json: Dict[str, Any], timeout: int = ...) -> Any: ...
    def put(self, url: str, json: Dict[str, Any], timeout: int = ...) -> Any: ...


def get_base_url() -> str:
    return (os.environ.get("INGESTION_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def get_mongo_uri() -> str:
    return os.environ.get("MONGO_URI") or "mongodb://localhost:27017/epi_os"


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
        timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()


def finalize_run(base_url: str, http: HttpClient, run_id: str, status: str, message: str = "") -> None:
    resp = http.put(f"{base_url}/api/v1/ingestion/runs/{run_id}/status",
                    json={"status": status, "message": message}, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()


def committed_batches(base_url: str, http: HttpClient, run_id: str, entity: str) -> set:
    resp = http.get(
        f"{base_url}/api/v1/ingestion/runs/{run_id}/entities/{entity}/committed-batches",
        timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return set(resp.json().get("batch_numbers", []))


# --- Extract + restore ---------------------------------------------------- #
def extract_archive(zip_path: str, work_dir: str) -> str:
    import zipfile
    os.makedirs(work_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(work_dir)
    return work_dir


def find_mongodump_archive(work_dir: str) -> str:
    """Locate the ``*.archive`` mongodump file inside the extracted dataset."""
    matches = glob.glob(os.path.join(work_dir, "**", "*.archive"), recursive=True)
    if not matches:
        raise FileNotFoundError(f"no mongodump *.archive found under {work_dir}")
    return sorted(matches, key=os.path.getsize, reverse=True)[0]


def build_mongorestore_cmd(archive_path: str, mongo_uri: str, staging_db: str = STAGING_DB,
                           repos: Optional[List[str]] = None) -> List[str]:
    """mongorestore the gzipped archive into the staging DB (ns-remapped).

    ``repos`` optionally limits the restore to specific Jira repos (collections) —
    a bounded/selective ingest (e.g. dev runs, or when disk can't hold all ~60 GB).
    When omitted, the full ``JiraReposAnon`` DB is restored.
    """
    cmd = ["mongorestore", "--gzip", f"--archive={archive_path}", f"--uri={mongo_uri}"]
    for repo in repos or []:
        cmd.append(f"--nsInclude=JiraReposAnon.{repo}")
    cmd += ["--nsFrom=JiraReposAnon.*", f"--nsTo={staging_db}.*", "--drop"]
    return cmd


def run_mongorestore(cmd: List[str], runner: Callable[[List[str]], Any] = None) -> None:
    """Execute mongorestore. ``runner`` is injectable for tests."""
    run = runner or (lambda c: subprocess.run(c, check=True, capture_output=True))
    run(cmd)


# --- Normalize Jira issues -> evidence collections ------------------------ #
def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return value if isinstance(value, datetime) else None
    v = value.replace("Z", "+00:00")
    # Jira uses e.g. 2021-01-02T03:04:05.000+0000 -> normalize the offset.
    if len(v) >= 5 and (v[-5] in "+-") and v[-3] != ":":
        v = v[:-2] + ":" + v[-2:]
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def _get(d: dict, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
    return cur if cur is not None else default


def _names(value: Any) -> List[str]:
    """Extract a list of names from a raw Jira list field, defensively.

    Handles the three shapes seen in the dataset: a list of objects each with a
    ``name`` (fixVersions / components), a list of bare strings (labels, or an
    occasional string entry), and absent/None/non-list values (-> ``[]``).
    Entries with no usable, non-empty string name are skipped.
    """
    if not isinstance(value, list):
        return []
    names: List[str] = []
    for entry in value:
        if isinstance(entry, dict):
            name = entry.get("name")
        else:
            name = entry
        if isinstance(name, str) and name.strip():
            names.append(name)
    return names


def transform_issue(issue: dict, project_key: str) -> Dict[str, List[dict]]:
    """Map one Jira issue document to our normalized evidence rows."""
    key = issue.get("key") or issue.get("id")
    fields = issue.get("fields", {}) or {}
    out: Dict[str, List[dict]] = {"issues": [], "issue_histories": [], "comments": [], "issue_links": []}

    out["issues"].append({
        "issue_key": key, "project_key": project_key,
        "status": _get(fields, "status", "name", default="Unknown"),
        "priority": _get(fields, "priority", "name"),
        "created_at": _parse_dt(fields.get("created")),
        "resolved_at": _parse_dt(fields.get("resolutiondate")),
        # Sub-project forecast subjects: release/component/tag scoping (capture-only).
        "fix_versions": _names(fields.get("fixVersions")),
        "components": _names(fields.get("components")),
        "labels": _names(fields.get("labels")),
    })

    for hist in _get(issue, "changelog", "histories", default=[]) or []:
        changed_at = _parse_dt(hist.get("created"))
        author = _get(hist, "author", "name") or _get(hist, "author", "displayName")
        for item in hist.get("items", []) or []:
            if item.get("field") == "status":
                out["issue_histories"].append({
                    "issue_key": key, "project_key": project_key, "field": "status",
                    "to_value": item.get("toString"), "changed_at": changed_at, "author": author})

    for c in _get(fields, "comment", "comments", default=[]) or []:
        out["comments"].append({
            "issue_key": key, "project_key": project_key,
            "author": _get(c, "author", "name") or _get(c, "author", "displayName"),
            "created_at": _parse_dt(c.get("created"))})

    for link in fields.get("issuelinks", []) or []:
        target = _get(link, "outwardIssue", "key") or _get(link, "inwardIssue", "key")
        if target:
            out["issue_links"].append({
                "source_issue_key": key, "target_issue_key": target,
                "link_type": _get(link, "type", "name", default="relates"), "project_key": project_key})
    return out


# --- Schema-mapping coverage (confirm the real dump matches transform_issue) - #
# The paths ``transform_issue`` reads out of a Jira issue document. If the real
# anonymized dump renames/flattens any of these, the corresponding evidence rows
# come out empty *without erroring* — so we measure presence explicitly and
# surface it (probe script offline; the normalize task through the governed log).
EXPECTED_PATHS: Dict[str, Callable[[dict], Any]] = {
    "key": lambda i: i.get("key") or i.get("id"),
    "fields": lambda i: i.get("fields") if isinstance(i.get("fields"), dict) else None,
    "fields.status.name": lambda i: _get(i, "fields", "status", "name"),
    "fields.priority.name": lambda i: _get(i, "fields", "priority", "name"),
    "fields.created": lambda i: _get(i, "fields", "created"),
    "fields.resolutiondate": lambda i: _get(i, "fields", "resolutiondate"),
    "changelog.histories": lambda i: _get(i, "changelog", "histories"),
    "fields.comment.comments": lambda i: _get(i, "fields", "comment", "comments"),
    "fields.issuelinks": lambda i: _get(i, "fields", "issuelinks"),
}


def field_presence(issue: dict) -> Dict[str, bool]:
    """Which of the paths transform_issue reads are actually present + truthy."""
    return {name: bool(fn(issue)) for name, fn in EXPECTED_PATHS.items()}


def issue_is_mapped(issue: dict) -> bool:
    """A doc is 'recognized' if we can pull an identity and a fields block from it.

    False means transform_issue would emit only a stub issue row (status Unknown,
    no dates/history/comments/links) — a shape mismatch, not a genuinely sparse issue.
    """
    return bool((issue.get("key") or issue.get("id")) and isinstance(issue.get("fields"), dict))


def batch_coverage(issues: List[dict]) -> Dict[str, Any]:
    """Aggregate path presence + unmapped count over a batch of raw issue docs."""
    present: Dict[str, int] = {name: 0 for name in EXPECTED_PATHS}
    unmapped = 0
    for issue in issues:
        if not issue_is_mapped(issue):
            unmapped += 1
        for name, is_present in field_presence(issue).items():
            if is_present:
                present[name] += 1
    return {"docs": len(issues), "unmapped": unmapped, "present": present}


def merge_coverage(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Combine two batch_coverage results into a running total."""
    present = {name: a["present"].get(name, 0) + b["present"].get(name, 0) for name in EXPECTED_PATHS}
    return {"docs": a["docs"] + b["docs"], "unmapped": a["unmapped"] + b["unmapped"], "present": present}


def iter_issue_batches(collection, batch_size: int = DEFAULT_BATCH_SIZE) -> Iterator[Tuple[int, int, List[dict]]]:
    """Stream issue docs from a staging collection in batches (batch_no, offset, docs)."""
    batch: List[dict] = []
    batch_no = 0
    offset = 0
    seen = 0
    for doc in collection.find({}):
        batch.append(doc)
        seen += 1
        if len(batch) >= batch_size:
            yield batch_no, offset, batch
            batch_no += 1
            offset = seen
            batch = []
    if batch:
        yield batch_no, offset, batch


def upsert_evidence(target_db, project_key: str, issues: List[dict]) -> int:
    """Normalize a batch of Jira issues and idempotently upsert evidence rows."""
    agg: Dict[str, List[dict]] = {"issues": [], "issue_histories": [], "comments": [], "issue_links": []}
    for issue in issues:
        for coll, rows in transform_issue(issue, project_key).items():
            agg[coll].extend(rows)
    for issue in agg["issues"]:
        target_db["issues"].update_one({"issue_key": issue["issue_key"]}, {"$set": issue}, upsert=True)
    # Replace child rows for these issues to stay idempotent on re-runs.
    keys = [i["issue_key"] for i in agg["issues"]]
    for coll in ("issue_histories", "comments", "issue_links"):
        field = "source_issue_key" if coll == "issue_links" else "issue_key"
        target_db[coll].delete_many({field: {"$in": keys}})
        if agg[coll]:
            target_db[coll].insert_many(agg[coll])
    target_db["projects"].update_one(
        {"project_key": project_key},
        {"$set": {"project_key": project_key, "name": project_key}}, upsert=True)
    return len(agg["issues"])
