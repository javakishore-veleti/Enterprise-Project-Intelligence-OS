"""Offline schema probe for the restored Jira staging DB.

Run this AFTER restoring even a single repo of the real dataset::

    mongorestore --gzip --archive=mongodump-JiraReposAnon.archive \\
      --nsInclude='JiraReposAnon.<repo>' --nsTo='jira_repos.<repo>'

    python -m project_dataset_ingest.probe_schema \\
      --uri mongodb://localhost:27017 --db jira_repos --sample 200

It samples documents from each staging collection and reports, per
``EXPECTED_PATHS`` (the exact paths ``transform_issue`` reads), what fraction of
sampled docs actually carry that path — plus a count of docs we can't map at
all. Anything below 100% is where the real anonymized dump diverges from the
standard-Jira shape the mapper assumes: that is the field mapping to fix in
``tasks.transform_issue`` before a full run. Nothing is written; read-only.

Exit code is non-zero if any collection has unmapped docs or a fully-absent
core path, so this doubles as a CI/gate check once a fixture DB exists.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from project_dataset_ingest import tasks

# Core paths whose total absence almost certainly means a shape mismatch (vs.
# genuinely-optional paths like comments/links/priority that a real issue may lack).
CORE_PATHS = ("key", "fields", "fields.status.name", "fields.created")


def probe_collection(collection, sample: int) -> Dict[str, Any]:
    """Read up to ``sample`` docs and aggregate path presence + one example."""
    cov = {"docs": 0, "unmapped": 0, "present": {}}
    example: Dict[str, Any] = {}
    docs: List[dict] = list(collection.find({}).limit(sample))
    if docs:
        cov = tasks.batch_coverage(docs)
        example = docs[0]
    return {"coverage": cov, "example": example}


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 1) if total else 0.0


def format_report(name: str, result: Dict[str, Any]) -> str:
    cov = result["coverage"]
    total = cov["docs"]
    lines = [f"\n=== {name}  (sampled {total} docs, {cov['unmapped']} unmapped) ==="]
    for path in tasks.EXPECTED_PATHS:
        count = cov["present"].get(path, 0)
        pct = _pct(count, total)
        flag = ""
        if total and count == 0 and path in CORE_PATHS:
            flag = "  <-- CORE PATH ABSENT: fix transform_issue mapping"
        elif total and pct < 100.0:
            flag = "  <-- partial (may be optional, confirm)"
        lines.append(f"  {path:<28} {pct:5.1f}%  ({count}/{total}){flag}")
    return "\n".join(lines)


def collection_has_problem(result: Dict[str, Any]) -> bool:
    cov = result["coverage"]
    if not cov["docs"]:
        return False
    if cov["unmapped"]:
        return True
    return any(cov["present"].get(p, 0) == 0 for p in CORE_PATHS)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe restored Jira staging schema vs transform_issue.")
    parser.add_argument("--uri", default=tasks.get_mongo_uri())
    parser.add_argument("--db", default=tasks.STAGING_DB)
    parser.add_argument("--sample", type=int, default=200, help="docs to sample per collection")
    parser.add_argument("--collection", default=None, help="probe just this one collection")
    parser.add_argument("--show-example", action="store_true", help="print one raw sample doc per collection")
    args = parser.parse_args(argv)

    from pymongo import MongoClient
    client = MongoClient(args.uri)
    problems = 0
    try:
        db = client[args.db]
        names = [args.collection] if args.collection else sorted(db.list_collection_names())
        if not names:
            print(f"no collections in {args.db!r}; restore a repo first.", file=sys.stderr)
            return 2
        for name in names:
            result = probe_collection(db[name], args.sample)
            print(format_report(name, result))
            if args.show_example and result["example"]:
                print("  example doc:\n" + json.dumps(result["example"], default=str, indent=2)[:2000])
            if collection_has_problem(result):
                problems += 1
    finally:
        client.close()

    if problems:
        print(f"\n{problems} collection(s) show a likely schema mismatch — see flags above.", file=sys.stderr)
        return 1
    print("\nAll sampled collections map cleanly to transform_issue.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
