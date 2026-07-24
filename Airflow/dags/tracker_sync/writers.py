"""Real ``EvidenceWriter`` + ``ProjectRegistrar`` implementations for the DAG.

Kept out of ``sync_engine`` (which stays infra-free/pure) so the engine unit-tests
with fakes. These carry the actual Mongo + Org-Management-API side effects and are
exercised live, not in the hermetic suite.
"""
from __future__ import annotations

from typing import Any, Dict, List

_CHILD_KEY = {"issue_histories": "issue_key", "comments": "issue_key", "issue_links": "source_issue_key"}


class MongoEvidenceWriter:
    """Idempotently upsert normalized+stamped evidence rows into the Mongo store.

    Mirrors ``project_dataset_ingest.tasks.upsert_evidence`` (upsert issues by
    issue_key; replace child rows for those issues to stay idempotent on re-run),
    but the rows arrive already stamped with org_id/root_org_id/repo_id and the
    project doc is stamped too. Never rewrites unrelated global docs.
    """

    def __init__(self, evidence_db: Any, repo_ctx: Dict[str, Any]) -> None:
        self._db = evidence_db
        self._ctx = repo_ctx

    def write(self, project_key: str, rows: Dict[str, List[dict]]) -> int:
        issues = rows.get("issues", [])
        for issue in issues:
            self._db["issues"].update_one(
                {"issue_key": issue["issue_key"]}, {"$set": issue}, upsert=True)
        keys = [i["issue_key"] for i in issues]
        for coll, key_field in _CHILD_KEY.items():
            batch = rows.get(coll, [])
            if keys:
                self._db[coll].delete_many({key_field: {"$in": keys}})
            if batch:
                self._db[coll].insert_many(batch)
        self._db["projects"].update_one(
            {"project_key": project_key},
            {"$set": {
                "project_key": project_key, "name": project_key,
                "org_id": self._ctx.get("org_id"),
                "root_org_id": self._ctx.get("root_org_id"),
                "repo_id": self._ctx.get("repo_id"),
            }},
            upsert=True)
        return len(issues)


class OrgApiProjectRegistrar:
    """Registers synced projects as ``tracker_projects`` under the repo via Org-API.

    Calls Org-Management-API ``POST /api/v1/repositories/{repo_id}/projects`` (the
    governed add-projects endpoint); idempotent there (ON CONFLICT upsert).
    """

    def __init__(self, base_url: str, http: Any, timeout: int = 60) -> None:
        self._base = base_url.rstrip("/")
        self._http = http
        self._timeout = timeout

    def register(self, repo_id: str, projects: List[Dict[str, str]]) -> None:
        if not projects:
            return
        payload = {"projects": [
            {"external_key": p["external_key"], "name": p.get("name")} for p in projects]}
        resp = self._http.post(
            f"{self._base}/api/v1/repositories/{repo_id}/projects",
            json=payload, timeout=self._timeout)
        resp.raise_for_status()
