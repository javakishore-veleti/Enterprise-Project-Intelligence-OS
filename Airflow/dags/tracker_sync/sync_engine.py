"""Pure, framework-free sync engine for tracker-repository sync.

Given a ``TrackerConnector`` + a repo context, this normalizes a repository's
projects/issues into the Mongo evidence store, in bounded idempotent batches,
stamping every written doc with ``org_id`` / ``root_org_id`` / ``repo_id`` for
attribution and future row-level hardening. Normalization reuses the SAME
``transform_issue`` the global batch-ingest path uses — one mapping, not two.

Nothing here imports Airflow, pymongo, or requests: the connector, the evidence
writer, and the project registrar are injected (real in the DAG, fakes in tests),
so the whole path is unit-testable with no infrastructure.

Invariants:
- **Additive stamping.** Synced docs gain org_id/root_org_id/repo_id; existing
  global docs are never rewritten by anything here — the writer upserts by
  issue_key, so a synced doc simply carries the extra fields.
- **Bounded + resumable.** Work is split into independent batch windows
  (offset/limit); a re-run skips already-committed batches (the DAG passes the
  committed set). Batches never depend on each other, so they parallelize.
- **Idempotent.** Upsert by issue_key; re-syncing the same window is a no-op.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol

from project_dataset_ingest.tasks import transform_issue

DEFAULT_BATCH_SIZE = 500

# Evidence collections a normalized issue fans out into (issue_links keys off the
# source issue; the rest key off issue_key).
_EVIDENCE_COLLECTIONS = ("issues", "issue_histories", "comments", "issue_links")


class EvidenceWriter(Protocol):
    """Persists a batch of already-normalized, already-stamped evidence rows."""

    def write(self, project_key: str, rows: Dict[str, List[dict]]) -> int:
        """Idempotently upsert ``rows`` for ``project_key``; return issues written."""


class ProjectRegistrar(Protocol):
    """Registers synced projects as ``tracker_projects`` under a repository."""

    def register(self, repo_id: str, projects: List[Dict[str, str]]) -> None: ...


# A per-batch progress callback: (project_key, batch_spec, result) -> None.
ProgressCallback = Callable[[str, Dict[str, Any], Dict[str, Any]], None]


def _stamp(doc: dict, repo_ctx: Dict[str, Any]) -> dict:
    """Additively stamp a doc with tenancy/attribution fields (never removes any)."""
    doc["org_id"] = repo_ctx.get("org_id")
    doc["root_org_id"] = repo_ctx.get("root_org_id")
    doc["repo_id"] = repo_ctx.get("repo_id")
    return doc


def transform_and_stamp(
    raw_issues: List[dict], project_key: str, repo_ctx: Dict[str, Any]
) -> Dict[str, List[dict]]:
    """Normalize raw issues via ``transform_issue`` and stamp every emitted row."""
    agg: Dict[str, List[dict]] = {c: [] for c in _EVIDENCE_COLLECTIONS}
    for issue in raw_issues:
        for coll, rows in transform_issue(issue, project_key).items():
            for row in rows:
                agg[coll].append(_stamp(row, repo_ctx))
    return agg


def plan_batches(total: int, batch_size: int = DEFAULT_BATCH_SIZE) -> List[Dict[str, int]]:
    """Split ``total`` issues into independent, parallelizable batch windows.

    Each window ``{batch_no, offset, limit}`` is self-contained (no window depends
    on another's result), so the DAG can fan them out with dynamic task mapping.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    windows: List[Dict[str, int]] = []
    batch_no = 0
    offset = 0
    while offset < total:
        windows.append({"batch_no": batch_no, "offset": offset, "limit": batch_size})
        batch_no += 1
        offset += batch_size
    return windows


def sync_batch_window(
    connector,
    repo_ctx: Dict[str, Any],
    project_key: str,
    window: Dict[str, int],
    evidence_writer: EvidenceWriter,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Fetch one batch window, normalize+stamp it, and upsert evidence.

    Returns ``{batch_no, source_offset, record_count, issues_written}``. Pure w.r.t.
    concurrency: it only touches its own window and upserts by issue_key, so it is
    safe to run alongside other windows of the same or a different project.
    """
    config = repo_ctx.get("connection_config") or {}
    raw = list(connector.fetch_issues(
        config, project_key, since=since,
        offset=window.get("offset"), limit=window.get("limit")))
    rows = transform_and_stamp(raw, project_key, repo_ctx)
    written = evidence_writer.write(project_key, rows)
    return {
        "batch_no": window.get("batch_no", 0),
        "source_offset": window.get("offset", 0),
        "record_count": len(raw),
        "issues_written": written,
    }


def sync_project(
    connector,
    repo_ctx: Dict[str, Any],
    project_key: str,
    evidence_writer: EvidenceWriter,
    since: Optional[datetime] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    committed_batches: Optional[set] = None,
    progress: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Sync one project in bounded batches; skip already-committed batches (resume)."""
    config = repo_ctx.get("connection_config") or {}
    total = connector.count_issues(config, project_key, since=since)
    windows = plan_batches(total, batch_size)
    already = committed_batches or set()
    issues_synced = 0
    batches_done = 0
    for window in windows:
        if window["batch_no"] in already:
            continue
        result = sync_batch_window(connector, repo_ctx, project_key, window, evidence_writer, since)
        issues_synced += result["record_count"]
        batches_done += 1
        if progress is not None:
            progress(project_key, window, result)
    return {
        "project_key": project_key,
        "issues_intended": total,
        "issues_synced": issues_synced,
        "batches_total": len(windows),
        "batches_done": batches_done,
    }


def sync_repository(
    connector,
    repo_ctx: Dict[str, Any],
    evidence_writer: EvidenceWriter,
    project_registrar: ProjectRegistrar,
    since: Optional[datetime] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Sync an entire repository end to end (the in-process, single-call path).

    Lists the connector's projects, registers them as ``tracker_projects`` under
    the repo, then normalizes + stamps + upserts each project's issues in bounded
    batches. ``repo_ctx`` = ``{org_id, root_org_id, repo_id, provider,
    connection_config}``. ``since`` (``None`` = full) enables end-of-day delta sync.

    The DAG uses the finer-grained ``plan_batches`` / ``sync_batch_window`` for
    concurrent per-project + per-batch execution; this convenience wrapper shares
    the exact same primitives so the behavior is identical. Returns
    ``{projects: [...], issues_synced, since}``.
    """
    projects = connector.list_projects(repo_ctx.get("connection_config") or {})
    # Register the discovered projects as tracker_projects under the repo (idempotent).
    project_registrar.register(repo_ctx["repo_id"], projects)

    per_project: List[Dict[str, Any]] = []
    issues_synced = 0
    for project in projects:
        key = project["external_key"]
        summary = sync_project(
            connector, repo_ctx, key, evidence_writer,
            since=since, batch_size=batch_size, progress=progress)
        issues_synced += summary["issues_synced"]
        per_project.append(summary)
    return {"projects": per_project, "issues_synced": issues_synced, "since": since}
