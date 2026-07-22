"""Deterministic digital-twin scenario mechanics (pure logic + bounded Mongo reads).

Two deterministic steps, NO LLM:

1. ``estimate_scenario_effect`` — read the free-text what-if for capacity / scope /
   deadline signals and translate them into a bounded on-time-probability delta.
   Pure keyword scoring, so it is fully unit-testable.
2. ``find_cascades`` — propagate the scenario's impact to OTHER projects that are
   structurally coupled to this one: cross-project dependency links (a blocks/
   depends-on edge whose target issue key belongs to another project) and shared
   contributors (authors active in both projects). Reads the evidence store the
   same bounded way the investigation tools do.

The LLM later narrates the trade-off; it never computes these deltas or targets.
"""
from __future__ import annotations

from typing import Any

# --- Scenario effect signals (capacity = verb + a staffing noun) -------------
_CAPACITY_NOUNS = (
    "engineer", "developer", " dev", "people", "person", "staff", "resource",
    "headcount", "team member", "teammate", "contributor", "hand", "body",
)
_ADD_VERBS = ("add", "more", "bring in", "hire", "extra", "reinforce", "onboard",
              "staff up", "increase", "grow the team", "additional")
_REMOVE_VERBS = ("move", "remove", "cut", "lose", "reassign", "pull", "reduce",
                 "fewer", "reallocate", "take away", "drop", "lend", "borrow",
                 "loan", "shift")
_DESCOPE = ("descope", "cut scope", "reduce scope", "defer", "drop feature",
            "remove feature", "narrow scope", "trim scope", "reduce requirement")
_ADD_SCOPE = ("add scope", "new feature", "expand scope", "extra feature",
              "add requirement", "widen scope", "grow scope", "additional feature")
_EXTEND = ("extend", "push out", "more time", "delay the deadline", "delay deadline",
           "slip the date", "additional time", "later deadline", "longer runway")
_COMPRESS = ("accelerate", "sooner", "pull in", "tighten", "compress",
             "earlier deadline", "crash the schedule", "crash schedule", "sprint harder")

_CAPACITY_STEP = 0.06
_CAPACITY_CAP = 0.18
_SCOPE_STEP = 0.08
_DEADLINE_STEP = 0.10
_MAX_ABS_DELTA = 0.30

_MAG_WEIGHT = {"high": 0.15, "medium": 0.08, "low": 0.03}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _first_int(text: str) -> int:
    token = ""
    for ch in text:
        if ch.isdigit():
            token += ch
        elif token:
            break
    return int(token) if token else 0


def estimate_scenario_effect(scenario: str) -> float:
    """Bounded on-time-probability delta implied by the what-if (deterministic).

    Capacity signals are a staffing noun paired with an add/remove verb (so
    "add 3 engineers" is +, "move 2 engineers to X" is -); scope and deadline
    signals are phrase matches. The delta scales with an engineer count when one
    is named, and is clamped to +/- 0.30.
    """
    t = (scenario or "").lower()
    n = _first_int(t) or 1
    delta = 0.0
    if any(noun in t for noun in _CAPACITY_NOUNS):
        if any(v in t for v in _ADD_VERBS):
            delta += min(_CAPACITY_STEP * n, _CAPACITY_CAP)
        if any(v in t for v in _REMOVE_VERBS):
            delta -= min(_CAPACITY_STEP * n, _CAPACITY_CAP)
    if any(k in t for k in _DESCOPE):
        delta += _SCOPE_STEP
    if any(k in t for k in _ADD_SCOPE):
        delta -= _SCOPE_STEP
    if any(k in t for k in _EXTEND):
        delta += _DEADLINE_STEP
    if any(k in t for k in _COMPRESS):
        delta -= _DEADLINE_STEP
    return round(_clamp(delta, -_MAX_ABS_DELTA, _MAX_ABS_DELTA), 3)


def _project_of(issue_key: str | None) -> str | None:
    """Derive the owning project key from a Jira-style issue key (PROJECT-123)."""
    if not issue_key or "-" not in issue_key:
        return None
    return issue_key.rsplit("-", 1)[0]


def _dep_magnitude(count: int) -> str:
    if count >= 5:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def _overlap_magnitude(ratio: float) -> str:
    if ratio >= 0.5:
        return "high"
    if ratio >= 0.2:
        return "medium"
    return "low"


def _rank(mag: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(mag, 0)


def find_cascades(db: Any, project_key: str, limit: int = 8) -> list[dict]:
    """Find projects the scenario propagates to (dependency + shared-contributor).

    Returns bounded cascade rows [{project_key, effect, reason, magnitude}] ranked
    by magnitude then project_key. Reads only counts + distinct authors — no raw
    records leave the store.
    """
    targets: dict[str, dict] = {}

    # 1. Cross-project dependency links (this project's issues block/depend on others).
    dep_counts: dict[str, int] = {}
    for link in db["issue_links"].find(
        {"project_key": project_key},
        {"_id": 0, "source_issue_key": 1, "target_issue_key": 1, "link_type": 1},
    ):
        other = _project_of(link.get("target_issue_key"))
        if other and other != project_key:
            dep_counts[other] = dep_counts.get(other, 0) + 1
    for other, count in dep_counts.items():
        mag = _dep_magnitude(count)
        targets[other] = {
            "project_key": other,
            "effect": "delivery slip risk",
            "reason": (f"{count} cross-project dependency link(s) tie {other} to "
                       f"{project_key}; a slip here propagates downstream."),
            "magnitude": mag,
        }

    # 2. Shared contributors (authors active in both projects -> capacity contention).
    source_authors = {
        a for a in db["issue_histories"].distinct("author", {"project_key": project_key})
        if a
    }
    if source_authors:
        other_projects = {
            p for p in db["issue_histories"].distinct("project_key")
            if p and p != project_key
        }
        for other in other_projects:
            other_authors = {
                a for a in db["issue_histories"].distinct("author", {"project_key": other})
                if a
            }
            shared = source_authors & other_authors
            if not shared:
                continue
            ratio = len(shared) / len(source_authors)
            mag = _overlap_magnitude(ratio)
            reason = (f"{len(shared)} contributor(s) work across {project_key} and "
                      f"{other} ({ratio:.0%} of this project's contributors).")
            existing = targets.get(other)
            if existing:
                # Coupled both ways: keep the stronger magnitude, note both channels.
                if _rank(mag) > _rank(existing["magnitude"]):
                    existing["magnitude"] = mag
                existing["effect"] = "delivery slip + capacity contention"
                existing["reason"] = existing["reason"] + " " + reason
            else:
                targets[other] = {
                    "project_key": other,
                    "effect": "capacity contention",
                    "reason": reason,
                    "magnitude": mag,
                }

    ordered = sorted(
        targets.values(),
        key=lambda c: (_rank(c["magnitude"]), c["project_key"]),
        reverse=True,
    )
    # reverse sorts project_key desc too; re-stabilize project_key ascending within rank
    ordered = sorted(ordered, key=lambda c: (-_rank(c["magnitude"]), c["project_key"]))
    return ordered[:limit]


def portfolio_risk_delta(probability_delta: float, cascades: list[dict]) -> float:
    """Net change in portfolio risk (>0 = portfolio risk increased).

    The source project's own risk change (``-probability_delta``) plus the
    magnitude-weighted spillover onto coupled projects.
    """
    spill = sum(_MAG_WEIGHT.get(c.get("magnitude", "low"), 0.0) for c in cascades)
    return round(-probability_delta + spill, 3)
