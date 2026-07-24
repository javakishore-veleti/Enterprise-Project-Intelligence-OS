"""FakeConnector — replay the restored ``jira_repos`` staging DB as a tracker.

This lets the ENTIRE live-ingest path (list projects -> plan batches -> fetch ->
normalize -> stamp -> upsert evidence -> register tracker_projects -> tracking log)
run end to end with NO live tracker. The staging DB is exactly the raw Jira-REST
dump the batch-ingest path already restores (``mongorestore`` of JiraReposAnon,
one collection per repo: Sakai, Spring, JFrog, ...), so the docs it yields are the
same raw shape ``transform_issue`` consumes.

``connection_config`` names which staging repo(s) to replay::

    {"fake_repos": ["Sakai", "Spring"]}

Distinct orgs point at distinct staging repos, so their imported project_keys
never collide. When ``fake_repos`` is omitted, every staging collection is replayed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from tracker_sync.connectors.base import TrackerConnector


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse a Jira timestamp (best-effort) for ``since`` comparisons."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    v = value.replace("Z", "+00:00")
    if len(v) >= 5 and (v[-5] in "+-") and v[-3] != ":":
        v = v[:-2] + ":" + v[-2:]
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def _updated_after(doc: Dict[str, Any], since: Optional[datetime]) -> bool:
    """True if the issue was updated at/after ``since`` (delta gate). No ``since`` = all."""
    if since is None:
        return True
    fields = doc.get("fields") or {}
    updated = _parse_dt(fields.get("updated") or fields.get("created"))
    if updated is None:
        return True  # can't tell -> include (safer to re-import than to drop)
    if updated.tzinfo and since.tzinfo is None:
        since = since.replace(tzinfo=updated.tzinfo)
    if since.tzinfo and updated.tzinfo is None:
        updated = updated.replace(tzinfo=since.tzinfo)
    return updated >= since


class FakeConnector(TrackerConnector):
    """A ``TrackerConnector`` backed by a Mongo-like ``jira_repos`` staging DB.

    ``staging_db`` is a handle where ``staging_db[collection].find({})`` yields the
    raw issue docs for that repo (a real ``pymongo`` DB in the DAG, a fake in tests).
    """

    provider = "fake"

    def __init__(self, staging_db: Any) -> None:
        self._staging = staging_db

    # --- config helpers ---
    def _repos(self, config: Dict[str, Any]) -> List[str]:
        repos = (config or {}).get("fake_repos")
        if repos:
            return list(repos)
        # No explicit list: replay every staging collection we can see.
        lister = getattr(self._staging, "list_collection_names", None)
        return sorted(lister()) if callable(lister) else []

    def _docs(self, project_key: str) -> List[Dict[str, Any]]:
        return list(self._staging[project_key].find({}))

    # --- TrackerConnector ---
    def test_connection(self, config: Dict[str, Any]) -> bool:
        return bool(self._repos(config))

    def list_projects(self, config: Dict[str, Any]) -> List[Dict[str, str]]:
        return [{"external_key": r, "name": r} for r in self._repos(config)]

    def count_issues(
        self, config: Dict[str, Any], project_key: str, since: Optional[datetime] = None
    ) -> int:
        return sum(1 for d in self._docs(project_key) if _updated_after(d, since))

    def fetch_issues(
        self,
        config: Dict[str, Any],
        project_key: str,
        since: Optional[datetime] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        # Stable order so offset/limit windows are deterministic + non-overlapping.
        docs = [d for d in self._docs(project_key) if _updated_after(d, since)]
        docs.sort(key=lambda d: str(d.get("key") or d.get("id") or ""))
        start = offset or 0
        end = start + limit if limit is not None else None
        for doc in docs[start:end]:
            yield doc
