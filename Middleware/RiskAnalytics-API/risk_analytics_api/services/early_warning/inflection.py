"""Deterministic early-warning inflection detection (pure Python, NO LLM).

Over a project's metric-history trajectory, find the metric with the biggest
recent ADVERSE move (on-time health dropping, velocity falling, blockers spiking,
reopen/aging/concentration/defects rising) and template a plain-language cause.
The service ranks detections across projects by severity x magnitude x recency.

Pure functions over plain dicts — fully unit-testable, and fast enough to run on
every read (no persistence, always-on).
"""
from __future__ import annotations

from dataclasses import dataclass


def _num(snap: dict, field_name: str, default: float = 0.0) -> float:
    v = snap.get(field_name, default)
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


# (field, adverse_direction, norm, label, cause-template)
# adverse_direction "up" -> rising is bad; "down" -> falling is bad.
_SPECS = (
    ("reopen_rate", "up", 0.15, "reopen rate",
     "Reopen churn jumped from {frm:.0%} to {to:.0%} — rework is climbing."),
    ("blocker_count", "up", 8.0, "open blockers",
     "Open blockers rose from {frm:.0f} to {to:.0f} — work is stalling."),
    ("issue_aging_days", "up", 60.0, "issue aging",
     "Average issue age rose from {frm:.0f} to {to:.0f} days — the backlog is stagnating."),
    ("backlog_growth", "up", 0.2, "backlog growth",
     "Backlog growth accelerated from {frm:.0%} to {to:.0%} month-over-month."),
    ("resolution_velocity", "down", 8.0, "resolution velocity",
     "Resolution velocity fell from {frm:.0f} to {to:.0f} issues per window — throughput is dropping."),
    ("contributor_concentration", "up", 0.2, "contributor concentration",
     "Contributor concentration rose from {frm:.0%} to {to:.0%} — bus-factor risk is increasing."),
    ("critical_defect_ratio", "up", 0.2, "critical-defect ratio",
     "Critical-defect ratio rose from {frm:.0%} to {to:.0%} — quality is degrading."),
)

_HIGH_T = 0.75
_MED_T = 0.35
_MIN_T = 0.08
_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


def _severity(normalized: float) -> str:
    if normalized >= _HIGH_T:
        return "high"
    if normalized >= _MED_T:
        return "medium"
    return "low"


@dataclass
class Inflection:
    """A detected adverse inflection (before ranking / DTO assembly)."""

    project_key: str
    metric: str
    from_value: float
    to_value: float
    direction: str          # literal movement of the metric (up|down)
    severity: str           # high|medium|low
    cause: str
    magnitude: float        # normalized adverse move (>= 0)
    from_computed_at: object
    to_computed_at: object

    @property
    def severity_rank(self) -> int:
        return _SEVERITY_RANK[self.severity]


def detect_inflection(project_key: str, history: list[dict]) -> Inflection | None:
    """Biggest recent adverse metric move for one project (latest vs prior snapshot).

    ``history`` is newest-first; needs >= 2 snapshots. Returns None if nothing
    moved adversely past the minimum threshold.
    """
    if len(history) < 2:
        return None
    latest, prior = history[0], history[1]

    best: Inflection | None = None
    for field_name, adverse_dir, norm, _label, template in _SPECS:
        cur = _num(latest, field_name)
        prev = _num(prior, field_name)
        adverse_move = (cur - prev) if adverse_dir == "up" else (prev - cur)
        normalized = adverse_move / norm if norm else 0.0
        if normalized < _MIN_T:
            continue
        inflection = Inflection(
            project_key=project_key,
            metric=field_name,
            from_value=round(prev, 4),
            to_value=round(cur, 4),
            direction="up" if cur > prev else "down",
            severity=_severity(normalized),
            cause=template.format(frm=prev, to=cur),
            magnitude=round(normalized, 4),
            from_computed_at=prior.get("computed_at"),
            to_computed_at=latest.get("computed_at"),
        )
        if best is None or inflection.magnitude > best.magnitude:
            best = inflection
    return best


def confidence_for(inf: Inflection, points: int) -> float:
    """Confidence in the inflection: stronger move + more trajectory points = higher."""
    base = 0.4 + min(inf.magnitude, 0.5)
    coverage = min(points / 5.0, 1.0)
    return round(max(0.1, min(0.95, base * (0.6 + 0.4 * coverage))), 3)
