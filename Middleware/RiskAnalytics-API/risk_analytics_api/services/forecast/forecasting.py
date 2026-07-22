"""Deterministic delivery-forecast math (pure Python, NO LLM).

This is the evidence-grounding boundary for the Predict engine: given a project's
metric-history trajectory (the ``project_metrics`` time series, newest-first) plus
its current open-work counts, it computes observable facts — an on-time
probability, a credible interval on it (a conformal-style band derived from the
historical variance + trend slope), a projected slip-days range, an outlook
bucket, and the drivers moving the forecast. The LLM later *interprets* these
facts; it never sees raw records and it never computes these numbers.

All functions are pure (no I/O), so the math is unit-testable with plain dicts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import pstdev

# --- Tuning constants (documented so the math is auditable) ----------------
_BLOCKER_NORM = 20.0        # blocker_count that saturates the blocker penalty
_AGING_NORM = 180.0         # issue_aging_days that saturates the aging penalty
_TREND_NORM = 10.0          # velocity-trend magnitude treated as "large"
_DEFAULT_STDEV = 0.15       # assumed health stdev when history is too short
_Z = 1.28                   # ~80% band multiplier on the health stdev
_BASE_SPREAD = 0.05         # irreducible interval half-width
_MAX_HALFWIDTH = 0.45
_MIN_HALFWIDTH = 0.03
_SLIP_HORIZON_DAYS = 120.0  # slip at on-time probability 0
_WINDOW_DAYS = 30.0         # a metric "window" ~ one month
_PER_BLOCKER_DAYS = 2.0
_MAX_SLIP_DAYS = 400
_MOVE_EPS = 0.01            # normalized magnitude below which a driver is dropped

#: The metric fields a forecast reads from each snapshot.
_FIELDS = (
    "reopen_rate", "blocker_count", "backlog_growth", "issue_aging_days",
    "resolution_velocity", "resolution_velocity_trend",
    "contributor_concentration", "critical_defect_ratio",
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _num(snap: dict, field_name: str, default: float = 0.0) -> float:
    v = snap.get(field_name, default)
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def health_score(snap: dict) -> float:
    """Metric-only delivery health in [0.02, 0.98] (higher = healthier).

    A weighted penalty over the adverse metrics, offset by the velocity trend.
    Used both as the on-time probability point estimate and as the per-snapshot
    series the interval's variance is measured over.
    """
    reopen = _clamp(_num(snap, "reopen_rate"), 0.0, 1.0)
    blocker = _clamp(_num(snap, "blocker_count") / _BLOCKER_NORM, 0.0, 1.0)
    backlog = _clamp(_num(snap, "backlog_growth"), 0.0, 1.0)
    aging = _clamp(_num(snap, "issue_aging_days") / _AGING_NORM, 0.0, 1.0)
    conc = _clamp(_num(snap, "contributor_concentration"), 0.0, 1.0)
    crit = _clamp(_num(snap, "critical_defect_ratio"), 0.0, 1.0)
    penalty = (
        0.28 * reopen + 0.22 * blocker + 0.16 * backlog
        + 0.12 * aging + 0.12 * conc + 0.10 * crit
    )
    trend = _clamp(_num(snap, "resolution_velocity_trend") / _TREND_NORM, -1.0, 1.0)
    return _clamp(1.0 - penalty + 0.10 * trend, 0.02, 0.98)


def interval_halfwidth(series: list[float]) -> float:
    """Credible-interval half-width from the health series (newest-first).

    Conformal-style: a base spread + a variance term (z * stdev of the health
    series) + a slope-uncertainty term (how fast health is moving per snapshot).
    Short history -> a wide default variance. Bounded to [0.03, 0.45].
    """
    if len(series) >= 2:
        stdev = pstdev(series)
        slope = abs(series[0] - series[-1]) / (len(series) - 1)
    else:
        stdev = _DEFAULT_STDEV
        slope = 0.0
    return _clamp(_BASE_SPREAD + _Z * stdev + 0.5 * slope, _MIN_HALFWIDTH, _MAX_HALFWIDTH)


def slip_center(p: float, snap: dict, project: dict) -> float:
    """Projected slip-days point estimate for an on-time probability ``p``.

    Blends a risk-based term ((1-p) * horizon), an open-work / velocity burn-down
    term, and a per-blocker drag. Bounded to [0, 400] days.
    """
    base = (1.0 - p) * _SLIP_HORIZON_DAYS
    velocity = _num(snap, "resolution_velocity")
    open_issues = float(project.get("open_issue_count", 0) or 0)
    if velocity > 0 and open_issues > 0:
        windows_to_clear = open_issues / velocity
        velocity_slip = max(0.0, windows_to_clear - 1.0) * _WINDOW_DAYS
    else:
        velocity_slip = (1.0 - p) * _SLIP_HORIZON_DAYS
    blocker_drag = _num(snap, "blocker_count") * _PER_BLOCKER_DAYS
    return _clamp(base + 0.5 * velocity_slip + blocker_drag, 0.0, float(_MAX_SLIP_DAYS))


def outlook_for(p: float) -> str:
    if p >= 0.66:
        return "on_track"
    if p >= 0.4:
        return "at_risk"
    return "off_track"


def _direction(x: float, eps: float) -> str:
    if x > eps:
        return "up"
    if x < -eps:
        return "down"
    return "flat"


def _word(x: float, up: str, down: str, flat: str, eps: float) -> str:
    if x > eps:
        return up
    if x < -eps:
        return down
    return flat


def drivers_from(latest: dict, prior: dict | None) -> list[dict]:
    """The factors moving the forecast, ranked by normalized magnitude (top 5).

    Delta-based factors (blocker burn-rate, reopen churn, aging) compare the
    latest snapshot to the prior one; rate factors (velocity trend, backlog
    growth) read the latest value directly. Factors that did not materially move
    are dropped.
    """
    cands: list[tuple[float, dict]] = []

    v = _num(latest, "resolution_velocity_trend")
    cands.append((abs(v) / _TREND_NORM, {
        "factor": "resolution_velocity",
        "direction": _direction(v, 0.5),
        "detail": (f"Resolution velocity "
                   f"{_word(v, 'accelerating', 'slowing', 'steady', 0.5)} "
                   f"({v:+.0f} issues vs the prior window)."),
    }))

    bg = _num(latest, "backlog_growth")
    cands.append((abs(bg), {
        "factor": "backlog_growth",
        "direction": _direction(bg, 0.005),
        "detail": (f"Backlog {_word(bg, 'growing', 'shrinking', 'flat', 0.005)} "
                   f"at {bg:+.0%} month-over-month."),
    }))

    delta_specs = (
        ("blocker_count", "blocker_burn_rate", _BLOCKER_NORM, "blockers",
         "piling up", "clearing", "{d:+.0f} open blocker(s)"),
        ("reopen_rate", "reopen_churn", 1.0, "reopen churn",
         "rising", "easing", "{d:+.0%} reopen rate"),
        ("issue_aging_days", "issue_aging", _AGING_NORM, "issue aging",
         "increasing", "decreasing", "{d:+.0f} days average age"),
    )
    for field_name, factor, norm, _label, up_w, down_w, fmt in delta_specs:
        cur = _num(latest, field_name)
        if prior is not None:
            delta = cur - _num(prior, field_name)
        else:
            delta = cur  # no prior -> treat current level as the movement proxy
        eps = norm * 0.01
        cands.append((abs(delta) / norm, {
            "factor": factor,
            "direction": _direction(delta, eps),
            "detail": (f"{factor.replace('_', ' ').capitalize()} "
                       f"{_word(delta, up_w, down_w, 'steady', eps)} "
                       f"({fmt.format(d=delta)})."),
        }))

    cands.sort(key=lambda kv: kv[0], reverse=True)
    return [d for mag, d in cands if mag >= _MOVE_EPS][:5]


@dataclass
class ForecastFacts:
    """Framework-free deterministic forecast the service maps onto the DTO."""

    on_time_probability: float
    probability_low: float
    probability_high: float
    projected_slip_days_low: int
    projected_slip_days_high: int
    outlook: str
    drivers: list[dict] = field(default_factory=list)
    #: The interval half-width (reused by the scenario simulator).
    halfwidth: float = 0.0
    #: Number of trajectory snapshots the forecast was computed over.
    trajectory_points: int = 0


def compute_forecast(history: list[dict], project: dict) -> ForecastFacts:
    """Compute the full deterministic forecast from the metric-history trajectory.

    ``history`` is the ``project_metrics`` time series newest-first; ``project``
    carries the current open-work counts. With no history a neutral, maximally
    uncertain forecast is returned (the caller lowers confidence accordingly).
    """
    if not history:
        return ForecastFacts(
            on_time_probability=0.5, probability_low=0.05, probability_high=0.95,
            projected_slip_days_low=0, projected_slip_days_high=_MAX_SLIP_DAYS // 2,
            outlook="at_risk", drivers=[], halfwidth=_MAX_HALFWIDTH, trajectory_points=0,
        )

    latest = history[0]
    prior = history[1] if len(history) > 1 else None
    series = [health_score(s) for s in history]

    p = health_score(latest)
    hw = interval_halfwidth(series)
    p_low = round(_clamp(p - hw, 0.01, 0.99), 3)
    p_high = round(_clamp(p + hw, 0.01, 0.99), 3)

    center = slip_center(p, latest, project)
    rel = _clamp(2.0 * hw, 0.1, 0.8)
    slip_low = int(round(max(0.0, center * (1.0 - rel))))
    slip_high = int(round(min(float(_MAX_SLIP_DAYS), center * (1.0 + rel))))

    return ForecastFacts(
        on_time_probability=round(p, 3),
        probability_low=p_low,
        probability_high=p_high,
        projected_slip_days_low=slip_low,
        projected_slip_days_high=slip_high,
        outlook=outlook_for(p),
        drivers=drivers_from(latest, prior),
        halfwidth=round(hw, 3),
        trajectory_points=len(history),
    )
