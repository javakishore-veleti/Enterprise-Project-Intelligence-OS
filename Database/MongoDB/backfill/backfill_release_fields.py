#!/usr/bin/env python3
"""Backfill release/component/tag fields onto already-ingested evidence issues.

Phase 2a taught ``transform_issue`` (Airflow ``project_dataset_ingest``) to capture
``fix_versions`` / ``components`` / ``labels`` onto every evidence issue it writes —
but only for *future* ingests. Evidence that was normalized before 2a has none of
these three arrays, so Release / Component / Tag can't yet be used as forecast
subjects on the existing corpus.

This script fills that gap without re-running ingestion: for each raw
``jira_repos.<repo>`` collection (the ``mongorestore``d Jira dump, one collection
per repo), it reads each issue's identity + its three list fields and ``$set``s
``fix_versions`` / ``components`` / ``labels`` on the matching ``epi_os.issues``
document (matched on ``issue_key == raw key``). It touches *only* those three
fields — nothing else on the evidence doc changes — and it never creates evidence
rows (a raw key with no evidence doc is simply skipped). That makes it idempotent:
re-running re-sets the same values.

The name-extraction (``extract_names``) mirrors Phase 2a's ``_names`` exactly:
each entry is a dict with a ``name`` (fixVersions / components) or a bare string
(labels); blanks / None / non-list values collapse to ``[]``.

Run it against the local infra (needs ``pymongo``; reuse the Projects-API venv):

    ./Middleware/Projects-API/.venv/bin/python \\
        Database/MongoDB/backfill/backfill_release_fields.py

Options (env / flags):
    MONGO_URI            Mongo connection string (default mongodb://localhost:27017)
    EVIDENCE_DB          evidence database         (default epi_os)
    STAGING_DB           raw dump database         (default jira_repos)
    --repos R1,R2        only these raw repo collections (default: all in STAGING_DB)
    --limit N            cap issues scanned per repo (0 = no cap; smoke-runs)
    --batch-size N       bulk-update batch size    (default 1000)
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, Iterable, Iterator, List, Optional

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_EVIDENCE_DB = "epi_os"
DEFAULT_STAGING_DB = "jira_repos"
DEFAULT_BATCH_SIZE = 1000

#: Only these three fields are read from the raw doc and written to evidence.
_RAW_PROJECTION = {"_id": 0, "key": 1, "id": 1,
                   "fields.fixVersions": 1, "fields.components": 1, "fields.labels": 1}


def extract_names(value: Any) -> List[str]:
    """Names from a raw Jira list field — identical semantics to Phase 2a ``_names``.

    A list of objects each with a ``name`` (fixVersions / components), a list of
    bare strings (labels), or absent/None/non-list -> ``[]``. Entries with no
    usable non-empty string name are skipped.
    """
    if not isinstance(value, list):
        return []
    names: List[str] = []
    for entry in value:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if isinstance(name, str) and name.strip():
            names.append(name)
    return names


def build_set(raw_issue: dict) -> Dict[str, List[str]]:
    """The ``$set`` document (the three subject fields) for one raw Jira issue."""
    fields = raw_issue.get("fields", {}) or {}
    return {
        "fix_versions": extract_names(fields.get("fixVersions")),
        "components": extract_names(fields.get("components")),
        "labels": extract_names(fields.get("labels")),
    }


def _raw_key(raw_issue: dict) -> Optional[str]:
    return raw_issue.get("key") or raw_issue.get("id")


def iter_raw_issues(collection, limit: int = 0) -> Iterator[dict]:
    """Stream raw issue docs (projected to identity + the three list fields)."""
    cursor = collection.find({}, _RAW_PROJECTION)
    if limit and limit > 0:
        cursor = cursor.limit(limit)
    return iter(cursor)


def backfill_collection(
    raw_coll, evidence_coll, *, batch_size: int = DEFAULT_BATCH_SIZE,
    limit: int = 0, log=print,
) -> Dict[str, int]:
    """Backfill the three subject fields from one raw repo collection into evidence.

    Matches evidence on ``issue_key == raw key`` and ``$set``s the three arrays,
    never upserting (missing evidence rows are skipped). Bounded/batched via
    bulk ``UpdateOne`` writes. Returns ``{scanned, matched, modified}`` counts.
    """
    from pymongo import UpdateOne  # lazy so the pure helpers import without pymongo

    scanned = matched = modified = 0
    ops: List[Any] = []

    def flush() -> None:
        nonlocal matched, modified
        if not ops:
            return
        result = evidence_coll.bulk_write(ops, ordered=False)
        matched += result.matched_count
        modified += result.modified_count
        ops.clear()

    for raw in iter_raw_issues(raw_coll, limit):
        key = _raw_key(raw)
        if not key:
            continue
        scanned += 1
        ops.append(UpdateOne({"issue_key": key}, {"$set": build_set(raw)}, upsert=False))
        if len(ops) >= batch_size:
            flush()
    flush()

    log(f"  scanned={scanned} matched={matched} modified={modified}")
    return {"scanned": scanned, "matched": matched, "modified": modified}


def _list_repo_collections(staging_db) -> List[str]:
    return sorted(n for n in staging_db.list_collection_names() if not n.startswith("system."))


def backfill_all(
    client, *, evidence_db: str, staging_db: str,
    repos: Optional[Iterable[str]] = None, batch_size: int = DEFAULT_BATCH_SIZE,
    limit: int = 0, log=print,
) -> Dict[str, int]:
    """Backfill every (or the selected) raw repo collection into evidence."""
    staging = client[staging_db]
    evidence = client[evidence_db]
    names = list(repos) if repos else _list_repo_collections(staging)
    totals = {"scanned": 0, "matched": 0, "modified": 0}
    for repo in names:
        log(f"backfilling {staging_db}.{repo} -> {evidence_db}.issues")
        counts = backfill_collection(
            staging[repo], evidence["issues"],
            batch_size=batch_size, limit=limit, log=log)
        for k in totals:
            totals[k] += counts[k]
    log(f"DONE repos={len(names)} scanned={totals['scanned']} "
        f"matched={totals['matched']} modified={totals['modified']}")
    return totals


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill release/component/tag evidence fields.")
    p.add_argument("--repos", default=None,
                   help="Comma-separated raw repo collection names (default: all).")
    p.add_argument("--limit", type=int, default=0,
                   help="Cap issues scanned per repo (0 = no cap; use for smoke-runs).")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    from pymongo import MongoClient

    args = _parse_args(argv)
    uri = os.getenv("MONGO_URI", DEFAULT_MONGO_URI)
    evidence_db = os.getenv("EVIDENCE_DB", DEFAULT_EVIDENCE_DB)
    staging_db = os.getenv("STAGING_DB", DEFAULT_STAGING_DB)
    repos = [r.strip() for r in args.repos.split(",") if r.strip()] if args.repos else None

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        backfill_all(
            client, evidence_db=evidence_db, staging_db=staging_db,
            repos=repos, batch_size=args.batch_size, limit=args.limit)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
