"""Deterministic portfolio risk ranking (no LLM).

Turns each project's latest computed metrics into a single composite
``risk_score`` in 0..100 (higher = riskier), bands it, ranks all scored
projects server-side, and returns only the top N. Pure Python — the scoring
math lives in small testable helpers.

Scoring formula
---------------
``risk_score`` is a weighted blend of five signals, each normalized and CLAMPED
to [0,1] so no single metric can dominate:

    reopen              = clamp01(reopen_rate)                           weight 0.20
    critical            = clamp01(critical_defect_ratio)                 weight 0.20
    blocker (log-scaled)= clamp01(log10(1+blocker_count)/log10(1+1000))  weight 0.25
    aging (capped)      = clamp01(issue_aging_days / 3650)               weight 0.20
    open_ratio          = clamp01(open_issue_count / issue_count)        weight 0.15

    risk_score = 100 * (0.20*reopen + 0.20*critical + 0.25*blocker
                        + 0.20*aging + 0.15*open_ratio)

Weights sum to 1.0, so the score is bounded to [0,100]. Blockers are
log-scaled (a project with 1000+ blockers saturates that term); aging is capped
at ~10 years. Bands: score >= 66 -> High, >= 33 -> Medium, else Low.

``overall_risk`` escalates to the worst band present: High if any project is
High-band, else Medium if any is Medium-band, else Low.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from projects_api.dtos.common import PortfolioScoredRow
from projects_api.dtos.responses import (
    PortfolioProjectSummary,
    PortfolioRiskBands,
    PortfolioScope,
    PortfolioSummaryResponse,
    PortfolioTotals,
)
from projects_api.interfaces.daos import PortfolioSummaryDao
from projects_api.interfaces.services import PortfolioSummaryService

# --- normalization tunables ------------------------------------------------ #
BLOCKER_LOG_CAP = 1000      # blockers at/above this saturate the blocker term
AGING_CAP_DAYS = 3650.0     # open-age (days) at/above this saturates the aging term

# --- signal weights (sum to 1.0) ------------------------------------------- #
W_REOPEN = 0.20
W_CRITICAL = 0.20
W_BLOCKER = 0.25
W_AGING = 0.20
W_OPEN = 0.15

HIGH_THRESHOLD = 66.0
MEDIUM_THRESHOLD = 33.0

_LOG_DEN = math.log10(1 + BLOCKER_LOG_CAP)


def _clamp01(value: float) -> float:
    return 0.0 if value < 0 else 1.0 if value > 1 else value


def _norm_blocker(blocker_count: int) -> float:
    return _clamp01(math.log10(1 + max(0, blocker_count)) / _LOG_DEN)


def _norm_aging(days: float) -> float:
    return _clamp01(days / AGING_CAP_DAYS)


def _open_ratio(open_issue_count: int, issue_count: int) -> float:
    return _clamp01(open_issue_count / issue_count) if issue_count > 0 else 0.0


def risk_score(row: PortfolioScoredRow) -> float:
    """Composite 0..100 risk score (higher = riskier). See module docstring."""
    score = 100.0 * (
        W_REOPEN * _clamp01(row.reopen_rate)
        + W_CRITICAL * _clamp01(row.critical_defect_ratio)
        + W_BLOCKER * _norm_blocker(row.blocker_count)
        + W_AGING * _norm_aging(row.issue_aging_days)
        + W_OPEN * _open_ratio(row.open_issue_count, row.issue_count)
    )
    return round(score, 1)


def risk_band(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "High"
    if score >= MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


# --- portfolio roll-up ----------------------------------------------------- #
# How much each band's projects count toward the severity-weighted mean, so a
# portfolio full of High-band projects rolls up higher than one with a single
# High outlier among many calm projects.
_BAND_WEIGHT = {"High": 3.0, "Medium": 2.0, "Low": 1.0}


def portfolio_score(scored: list[tuple[float, str]]) -> float:
    """Aggregate 0..100 roll-up of a scope's projects (higher = riskier).

    ``scored`` is a list of ``(risk_score, risk_band)`` for every scored project.
    Formula (documented so the UI/tests can rely on it):

        portfolio_score = 0.6 * max(risk_score)
                        + 0.4 * severity_weighted_mean(risk_score)

    where the weighted mean weights High-band projects 3x, Medium 2x, Low 1x.
    The ``max`` term ensures a single High-band project keeps the portfolio hot;
    the weighted mean ensures many High-band projects dominate a few. Both terms
    are in [0,100], so the result is bounded to [0,100]. Empty scope -> 0.0.
    """
    if not scored:
        return 0.0
    max_score = max(score for score, _ in scored)
    weight_sum = sum(_BAND_WEIGHT[band] for _, band in scored)
    weighted_mean = sum(score * _BAND_WEIGHT[band] for score, band in scored) / weight_sum
    return round(0.6 * max_score + 0.4 * weighted_mean, 1)


def build_headline(row: PortfolioScoredRow) -> str:
    """Deterministic phrase from the project's 2-3 strongest weighted signals,
    e.g. ``"608 blockers · 32% reopen · 2067d aging"``."""
    candidates = [
        (W_BLOCKER * _norm_blocker(row.blocker_count), f"{row.blocker_count} blockers"),
        (W_REOPEN * _clamp01(row.reopen_rate), f"{round(row.reopen_rate * 100)}% reopen"),
        (W_AGING * _norm_aging(row.issue_aging_days), f"{round(row.issue_aging_days)}d aging"),
        (W_CRITICAL * _clamp01(row.critical_defect_ratio),
         f"{round(row.critical_defect_ratio * 100)}% critical"),
        (W_OPEN * _open_ratio(row.open_issue_count, row.issue_count),
         f"{round(_open_ratio(row.open_issue_count, row.issue_count) * 100)}% open"),
    ]
    ranked = [text for contrib, text in sorted(candidates, key=lambda c: c[0], reverse=True)
              if contrib > 0][:3]
    return " · ".join(ranked) if ranked else "no significant risk signals"


class DefaultPortfolioSummaryService(PortfolioSummaryService):
    def __init__(self, dao: PortfolioSummaryDao) -> None:
        self._dao = dao

    def summarize(
        self,
        top: int,
        project_keys: list[str] | None = None,
        user_key: str | None = None,
        scoped: bool = False,
    ) -> PortfolioSummaryResponse:
        data = self._dao.portfolio_data(project_keys)

        scored: list[tuple[float, str, PortfolioScoredRow]] = []
        high = medium = low = 0
        for row in data.scored:
            score = risk_score(row)
            band = risk_band(score)
            if band == "High":
                high += 1
            elif band == "Medium":
                medium += 1
            else:
                low += 1
            scored.append((score, band, row))

        # Rank server-side, descending by score; project_key breaks ties so the
        # ordering (and thus the top-N slice) is deterministic.
        scored.sort(key=lambda t: (-t[0], t[2].project_key))

        top_projects = [
            PortfolioProjectSummary(
                project_key=row.project_key,
                name=row.name,
                category=row.category,
                risk_score=score,
                risk_band=band,
                issue_count=row.issue_count,
                open_issue_count=row.open_issue_count,
                blocker_count=row.blocker_count,
                reopen_rate=row.reopen_rate,
                issue_aging_days=row.issue_aging_days,
                critical_defect_ratio=row.critical_defect_ratio,
                headline=build_headline(row),
            )
            for score, band, row in scored[:top]
        ]

        unscored = max(0, data.total_projects - len(data.scored))
        overall = "High" if high else "Medium" if medium else "Low"
        roll_up = portfolio_score([(s, b) for s, b, _ in scored])

        return PortfolioSummaryResponse(
            scope=PortfolioScope(
                user_key=user_key,
                project_count=data.total_projects,
                scoped=scoped,
            ),
            portfolio_score=roll_up,
            overall_risk=overall,
            totals=PortfolioTotals(
                projects=data.total_projects,
                issues=data.total_issues,
                open_issues=data.total_open_issues,
            ),
            risk_bands=PortfolioRiskBands(high=high, medium=medium, low=low, unscored=unscored),
            top_projects=top_projects,
            computed_at=datetime.now(timezone.utc).isoformat(),
        )
