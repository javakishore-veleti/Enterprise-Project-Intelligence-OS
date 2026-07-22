"""Evidence-store tools for the Investigation Agent.

Each tool is a **pure function of (db, project_key, params)** over the MongoDB
evidence store for ONE project, returning BOUNDED evidence — a count plus a small
capped sample, never a full dump. This honours the evidence-grounding invariant:
raw records are never handed to the LLM, only these bounded, deterministic facts.

Because every tool takes an explicit ``db`` handle, each is unit-testable with a
fake Mongo (no real infra). ``build_investigation_tools`` binds the ``db`` +
``project_key`` and exposes the LLM-facing params as LangChain ``StructuredTool``
objects the agent can call.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.tools import StructuredTool

# Shared vocabulary — mirrors Projects-API metrics computation so the tools read
# the same evidence the deterministic metrics were computed from.
CLOSED_STATES = ["Resolved", "Closed", "Done"]
REOPEN_VALUES = ["Reopened", "Open", "Reopen"]
BLOCKING_LINKS = ["blocks", "is blocked by", "depends on", "Blocks", "Depends"]
CRITICAL_PRIORITIES = ["Blocker", "Critical"]

#: Hard cap on any sample a tool returns (bounded evidence invariant).
MAX_SAMPLE = 25

#: The metric fields surfaced by ``metrics_snapshot`` (the 8 computed facts + trend).
_METRIC_FIELDS = (
    "blocker_count",
    "reopen_rate",
    "issue_aging_days",
    "resolution_velocity",
    "resolution_velocity_trend",
    "contributor_concentration",
    "dependency_depth",
    "critical_defect_ratio",
    "backlog_growth",
)


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _cap(limit: int) -> int:
    return max(1, min(int(limit), MAX_SAMPLE))


def metrics_snapshot(db: Any, project_key: str) -> dict:
    """Latest deterministic computed metrics for the project (from project_metrics)."""
    doc = db["project_metrics"].find_one(
        {"project_key": project_key}, sort=[("computed_at", -1)]
    ) or {}
    metrics = {field: doc.get(field) for field in _METRIC_FIELDS}
    return {"project_key": project_key, "metrics": metrics,
            "computed_at": _iso(doc.get("computed_at"))}


def reopened_issues(db: Any, project_key: str, limit: int = 10) -> dict:
    """Issues whose status history shows a reopen (Done/Closed -> back to open)."""
    cap = _cap(limit)
    hist = db["issue_histories"]
    query = {"project_key": project_key, "field": "status", "to_value": {"$in": REOPEN_VALUES}}
    keys = hist.distinct("issue_key", query)
    cursor = hist.find(
        query, {"_id": 0, "issue_key": 1, "to_value": 1, "changed_at": 1, "author": 1}
    ).sort("changed_at", -1).limit(cap)
    sample = [
        {"issue_key": d.get("issue_key"), "to_value": d.get("to_value"),
         "changed_at": _iso(d.get("changed_at")), "author": d.get("author")}
        for d in cursor
    ]
    return {"count": len(keys), "sample": sample}


def blocker_issues(db: Any, project_key: str, limit: int = 10) -> dict:
    """Open Blocker/Critical-priority issues currently constraining the project."""
    cap = _cap(limit)
    issues = db["issues"]
    query = {"project_key": project_key, "priority": {"$in": CRITICAL_PRIORITIES},
             "status": {"$nin": CLOSED_STATES}}
    count = issues.count_documents(query)
    cursor = issues.find(
        query, {"_id": 0, "issue_key": 1, "priority": 1, "status": 1, "created_at": 1}
    ).sort("created_at", 1).limit(cap)
    sample = [
        {"issue_key": d.get("issue_key"), "priority": d.get("priority"),
         "status": d.get("status"), "created_at": _iso(d.get("created_at"))}
        for d in cursor
    ]
    return {"count": count, "sample": sample}


def aging_issues(db: Any, project_key: str, limit: int = 10) -> dict:
    """Oldest still-open issues by creation date (the aging backlog)."""
    cap = _cap(limit)
    issues = db["issues"]
    query = {"project_key": project_key, "status": {"$nin": CLOSED_STATES},
             "created_at": {"$ne": None}}
    count = issues.count_documents(query)
    cursor = issues.find(
        query, {"_id": 0, "issue_key": 1, "status": 1, "created_at": 1}
    ).sort("created_at", 1).limit(cap)
    sample = [
        {"issue_key": d.get("issue_key"), "status": d.get("status"),
         "created_at": _iso(d.get("created_at"))}
        for d in cursor
    ]
    return {"count": count, "sample": sample}


def dependency_links(db: Any, project_key: str, limit: int = 10) -> dict:
    """Blocks / blocked-by / depends-on links (the dependency picture)."""
    cap = _cap(limit)
    links = db["issue_links"]
    query = {"project_key": project_key, "link_type": {"$in": BLOCKING_LINKS}}
    count = links.count_documents(query)
    cursor = links.find(
        query, {"_id": 0, "source_issue_key": 1, "target_issue_key": 1, "link_type": 1}
    ).limit(cap)
    sample = [
        {"source": d.get("source_issue_key"), "target": d.get("target_issue_key"),
         "link_type": d.get("link_type")}
        for d in cursor
    ]
    return {"count": count, "sample": sample}


def contributor_breakdown(db: Any, project_key: str, limit: int = 10) -> dict:
    """Top contributors by change authorship + the top contributor's share (bus-factor)."""
    cap = _cap(limit)
    counts: dict[str, int] = {}
    for coll, field in (("issue_histories", "author"), ("comments", "author")):
        for d in db[coll].find({"project_key": project_key}, {"_id": 0, field: 1}):
            author = d.get(field)
            if author:
                counts[author] = counts.get(author, 0) + 1
    total = sum(counts.values())
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top = [{"author": a, "changes": n} for a, n in ranked[:cap]]
    concentration = round(ranked[0][1] / total, 3) if total else 0.0
    return {"total_changes": total, "contributors": len(counts),
            "concentration": concentration, "top": top}


def status_change_timeline(db: Any, project_key: str, limit: int = 15) -> dict:
    """Most recent status changes across the project (what changed lately)."""
    cap = _cap(limit)
    hist = db["issue_histories"]
    query = {"project_key": project_key, "field": "status"}
    count = hist.count_documents(query)
    cursor = hist.find(
        query, {"_id": 0, "issue_key": 1, "to_value": 1, "changed_at": 1, "author": 1}
    ).sort("changed_at", -1).limit(cap)
    sample = [
        {"issue_key": d.get("issue_key"), "to_value": d.get("to_value"),
         "changed_at": _iso(d.get("changed_at")), "author": d.get("author")}
        for d in cursor
    ]
    return {"count": count, "sample": sample}


def build_investigation_tools(db: Any, project_key: str) -> list[StructuredTool]:
    """Bind ``db`` + ``project_key`` and expose the tools as LangChain StructuredTools.

    The LLM sees only the free params (``limit``); the Mongo handle and project
    scope are closed over, so the agent can never widen scope beyond one project.
    """

    def _metrics_snapshot() -> dict:
        """Latest computed metrics for the project (blocker_count, reopen_rate,
        issue_aging_days, resolution_velocity + trend, contributor_concentration,
        dependency_depth, critical_defect_ratio, backlog_growth)."""
        return metrics_snapshot(db, project_key)

    def _reopened_issues(limit: int = 10) -> dict:
        """Count + sample of issues that were reopened (Done/Closed -> back to open)."""
        return reopened_issues(db, project_key, limit)

    def _blocker_issues(limit: int = 10) -> dict:
        """Count + sample of open Blocker/Critical-priority issues."""
        return blocker_issues(db, project_key, limit)

    def _aging_issues(limit: int = 10) -> dict:
        """Count + sample of the oldest open issues by creation date."""
        return aging_issues(db, project_key, limit)

    def _dependency_links(limit: int = 10) -> dict:
        """Count + sample of blocks/blocked-by/depends-on links for the project."""
        return dependency_links(db, project_key, limit)

    def _contributor_breakdown(limit: int = 10) -> dict:
        """Top contributors by change authorship + the concentration ratio (bus-factor)."""
        return contributor_breakdown(db, project_key, limit)

    def _status_change_timeline(limit: int = 15) -> dict:
        """Count + sample of the most recent status changes in the project."""
        return status_change_timeline(db, project_key, limit)

    factories = [
        (_metrics_snapshot, "metrics_snapshot"),
        (_reopened_issues, "reopened_issues"),
        (_blocker_issues, "blocker_issues"),
        (_aging_issues, "aging_issues"),
        (_dependency_links, "dependency_links"),
        (_contributor_breakdown, "contributor_breakdown"),
        (_status_change_timeline, "status_change_timeline"),
    ]
    return [
        StructuredTool.from_function(func=fn, name=name, description=fn.__doc__)
        for fn, name in factories
    ]
