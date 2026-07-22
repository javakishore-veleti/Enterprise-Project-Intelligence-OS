"""Deterministic forecast inputs over a *filtered* evidence issue set (no LLM).

When a forecast is scoped to a Release / Component / Tag rather than a whole
project, there is no per-subject ``project_metrics`` trajectory to read. So this
module computes — purely, from the filtered ``issues`` (+ their status
``issue_histories``) — the same input signals the project-level forecaster reads
off a metrics snapshot: open/total counts, a blocker proxy (priority), a reopen
proxy (status history), issue aging (created_at), and a velocity/throughput proxy
(resolved_at over a recent window). The result is one synthetic snapshot + a
project-shaped counts dict that ``forecasting.compute_forecast`` consumes exactly
like the real trajectory — so the credible interval + drivers + narration pipeline
is reused unchanged.

All functions are pure (plain dicts / datetimes in), so the math is unit-testable.
"""
from __future__ import annotations

from datetime import datetime, timedelta

#: Mirrors the deterministic metric-computation vocabulary (Projects-API).
CLOSED_STATES = frozenset({"Resolved", "Closed", "Done"})
REOPEN_VALUES = frozenset({"Reopened", "Open", "Reopen"})
CRITICAL_PRIORITIES = frozenset({"Blocker", "Critical"})
BLOCKER_PRIORITY = "Blocker"
WINDOW_DAYS = 30

#: Below this many issues a subject subset is "tiny" — the caller widens the
#: interval and lowers confidence (thin evidence).
TINY_SUBSET = 10

#: subject_type -> the evidence issue array field it filters on.
FIELD_BY_SUBJECT = {
    "release": "fix_versions",
    "component": "components",
    "tag": "labels",
}


def _is_open(issue: dict) -> bool:
    return issue.get("status") not in CLOSED_STATES


def _reference_date(issues: list[dict]) -> datetime | None:
    """Latest issue ``created_at`` in the subset — the data-relative 'now'."""
    dates = [i.get("created_at") for i in issues if isinstance(i.get("created_at"), datetime)]
    return max(dates) if dates else None


def _avg_open_age_days(issues: list[dict], reference: datetime) -> float:
    ages = [
        (reference - i["created_at"]).total_seconds() / 86400.0
        for i in issues
        if _is_open(i) and isinstance(i.get("created_at"), datetime)
    ]
    return round(sum(ages) / len(ages), 1) if ages else 0.0


def _resolved_between(issues: list[dict], start: datetime, end: datetime) -> int:
    return sum(
        1 for i in issues
        if isinstance(i.get("resolved_at"), datetime) and start <= i["resolved_at"] <= end
    )


def _created_between(issues: list[dict], start: datetime, end: datetime) -> int:
    return sum(
        1 for i in issues
        if isinstance(i.get("created_at"), datetime) and start <= i["created_at"] <= end
    )


def _top_contributor_share(histories: list[dict]) -> float:
    """Top author's share of status-history activity (comments are absent dataset-wide)."""
    counts: dict[str, int] = {}
    for h in histories:
        author = h.get("author")
        if author:
            counts[author] = counts.get(author, 0) + 1
    total = sum(counts.values())
    return round(max(counts.values()) / total, 3) if total else 0.0


def compute_subset_signals(
    issues: list[dict], histories: list[dict]
) -> tuple[dict, dict]:
    """Compute a synthetic metrics snapshot + project counts over a filtered subset.

    ``issues`` are the evidence issue docs in scope (``{status, priority,
    created_at, resolved_at, issue_key}``); ``histories`` are their status-change
    rows (``{to_value, author}``). Returns ``(snapshot, project)`` where
    ``snapshot`` has the ``project_metrics`` field names and ``project`` carries
    ``open_issue_count`` / ``issue_count`` — the two inputs ``compute_forecast``
    reads.
    """
    total = len(issues)
    open_count = sum(1 for i in issues if _is_open(i))
    resolved_count = total - open_count

    blocker_count = sum(
        1 for i in issues if _is_open(i) and i.get("priority") == BLOCKER_PRIORITY
    )
    critical_open = sum(
        1 for i in issues if _is_open(i) and i.get("priority") in CRITICAL_PRIORITIES
    )

    reopened = len({
        h.get("issue_key") for h in histories
        if h.get("to_value") in REOPEN_VALUES and h.get("issue_key")
    })

    ref = _reference_date(issues)
    if ref is not None:
        start = ref - timedelta(days=WINDOW_DAYS)
        prior_start = ref - timedelta(days=2 * WINDOW_DAYS)
        created_w = _created_between(issues, start, ref)
        resolved_w = _resolved_between(issues, start, ref)
        resolved_prior = _resolved_between(issues, prior_start, start)
        aging = _avg_open_age_days(issues, ref)
        growth = round((created_w - resolved_w) / max(1, open_count), 3)
    else:
        resolved_w = resolved_prior = 0
        aging = 0.0
        growth = 0.0

    snapshot = {
        "backlog_growth": growth,
        "reopen_rate": round(reopened / max(1, resolved_count), 3),
        "blocker_count": blocker_count,
        "dependency_depth": 0,  # links are not scoped to a subject subset
        "issue_aging_days": aging,
        "resolution_velocity": float(resolved_w),
        "resolution_velocity_trend": float(resolved_w - resolved_prior),
        "contributor_concentration": _top_contributor_share(histories),
        "critical_defect_ratio": round(critical_open / max(1, open_count), 3),
    }
    project = {"issue_count": total, "open_issue_count": open_count}
    return snapshot, project
