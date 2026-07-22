"""Unit tests for the portfolio-summary service against an in-memory fake DAO."""
from __future__ import annotations

from datetime import date

from projects_api.dtos.common import PortfolioAggregate, PortfolioScoredRow
from projects_api.interfaces.daos import PortfolioSummaryDao
from projects_api.services.portfolio_summary import (
    DefaultPortfolioSummaryService,
    build_headline,
    portfolio_score,
    risk_band,
    risk_score,
)


class FakePortfolioSummaryDao(PortfolioSummaryDao):
    """In-memory fake that honors the DB-side ``project_keys`` scoping filter AND
    the ``as_of`` snapshot filter so both behaviours are actually exercised (not
    just passed through).

    ``snapshot_dates`` maps a project_key to the date of its latest metrics
    snapshot; when ``as_of`` is given only projects whose snapshot lands on/before
    that date stay scored (mirroring the DB ``$match`` on ``computed_at``). Totals
    come from the (time-independent) projects roll-up, so ``as_of`` only trims the
    scored rows — dropped projects become ``unscored``.
    """

    def __init__(
        self,
        aggregate: PortfolioAggregate,
        snapshot_dates: dict[str, date] | None = None,
    ) -> None:
        self._aggregate = aggregate
        self._snapshot_dates = snapshot_dates or {}
        self.last_as_of: date | None = None

    def portfolio_data(
        self,
        project_keys: list[str] | None = None,
        as_of: date | None = None,
    ) -> PortfolioAggregate:
        self.last_as_of = as_of
        scored = list(self._aggregate.scored)
        total_projects = self._aggregate.total_projects
        total_issues = self._aggregate.total_issues
        total_open = self._aggregate.total_open_issues
        if project_keys is not None:
            allowed = set(project_keys)
            scored = [r for r in scored if r.project_key in allowed]
            # Totals recomputed over the scoped rows (mirrors the DB $match).
            total_projects = len(scored)
            total_issues = sum(r.issue_count for r in scored)
            total_open = sum(r.open_issue_count for r in scored)
        if as_of is not None:
            scored = [
                r for r in scored
                if r.project_key in self._snapshot_dates
                and self._snapshot_dates[r.project_key] <= as_of
            ]
        return PortfolioAggregate(
            total_projects=total_projects,
            total_issues=total_issues,
            total_open_issues=total_open,
            scored=scored,
        )


def _row(key: str, **kw) -> PortfolioScoredRow:
    base = dict(
        project_key=key, name=f"{key} name", category="apache",
        issue_count=100, open_issue_count=40, blocker_count=0,
        reopen_rate=0.0, issue_aging_days=0.0, critical_defect_ratio=0.0,
    )
    base.update(kw)
    return PortfolioScoredRow(**base)


# A clearly-high-risk project: many blockers, high reopen/critical, very old, all open.
HIGH = _row("HIGH", issue_count=100, open_issue_count=100, blocker_count=800,
            reopen_rate=0.9, issue_aging_days=3650, critical_defect_ratio=0.9)
# A clearly-low-risk project: no adverse signals (nothing open either).
LOW = _row("LOW", issue_count=100, open_issue_count=0, blocker_count=0,
           reopen_rate=0.0, issue_aging_days=0.0, critical_defect_ratio=0.0)
# A middling project.
MID = _row("MID", issue_count=100, open_issue_count=60, blocker_count=30,
           reopen_rate=0.4, issue_aging_days=1000, critical_defect_ratio=0.3)


# --- pure scoring helpers -------------------------------------------------- #
def test_risk_score_bounds_and_ordering() -> None:
    hi, mid, lo = risk_score(HIGH), risk_score(MID), risk_score(LOW)
    assert 0.0 <= lo < mid < hi <= 100.0
    assert lo == 0.0                       # no adverse signals -> zero
    assert hi > 66.0                       # saturated signals -> High band


def test_risk_score_clamps_out_of_range_ratios() -> None:
    # reopen_rate > 1 must not let one metric blow past its weight share (0.20*100=20)
    weird = _row("WEIRD", issue_count=100, open_issue_count=0, blocker_count=0,
                 reopen_rate=5.0, issue_aging_days=0.0, critical_defect_ratio=0.0)
    assert risk_score(weird) == 20.0


def test_risk_band_thresholds() -> None:
    assert risk_band(66.0) == "High"
    assert risk_band(65.9) == "Medium"
    assert risk_band(33.0) == "Medium"
    assert risk_band(32.9) == "Low"
    assert risk_band(0.0) == "Low"


def test_build_headline_uses_strongest_signals() -> None:
    row = _row("H", issue_count=1000, open_issue_count=320, blocker_count=608,
               reopen_rate=0.32, issue_aging_days=2067, critical_defect_ratio=0.0)
    headline = build_headline(row)
    parts = headline.split(" · ")
    assert len(parts) == 3                 # top 3 signals only
    assert "608 blockers" in headline
    assert "32% reopen" in headline
    assert "2067d aging" in headline


def test_build_headline_no_signals() -> None:
    assert build_headline(LOW) == "no significant risk signals"


# --- service: ranking, banding, top-N, unscored ---------------------------- #
def _service(scored, total_projects, total_issues=0, total_open=0):
    agg = PortfolioAggregate(
        total_projects=total_projects, total_issues=total_issues,
        total_open_issues=total_open, scored=scored,
    )
    return DefaultPortfolioSummaryService(FakePortfolioSummaryDao(agg))


def test_summarize_ranks_descending_and_applies_top_n() -> None:
    # total_projects 5 => 2 unscored (only 3 have metrics)
    result = _service([LOW, HIGH, MID], total_projects=5,
                      total_issues=500, total_open=101).summarize(top=2)

    assert [p.project_key for p in result.top_projects] == ["HIGH", "MID"]
    assert result.top_projects[0].risk_score >= result.top_projects[1].risk_score
    assert result.top_projects[0].risk_band == "High"

    assert result.totals.projects == 5
    assert result.totals.issues == 500
    assert result.totals.open_issues == 101

    assert result.risk_bands.high == 1
    assert result.risk_bands.medium == 1
    assert result.risk_bands.low == 1
    assert result.risk_bands.unscored == 2      # 5 total - 3 scored


def test_summarize_overall_risk_escalates_to_worst_band() -> None:
    assert _service([HIGH, MID, LOW], 3).summarize(10).overall_risk == "High"
    assert _service([MID, LOW], 3).summarize(10).overall_risk == "Medium"
    assert _service([LOW], 3).summarize(10).overall_risk == "Low"


def test_summarize_top_n_larger_than_scored_returns_all() -> None:
    result = _service([HIGH, LOW], total_projects=2).summarize(top=50)
    assert len(result.top_projects) == 2
    assert result.risk_bands.unscored == 0


def test_summarize_empty_portfolio() -> None:
    result = _service([], total_projects=0).summarize(top=10)
    assert result.top_projects == []
    assert result.overall_risk == "Low"
    assert result.risk_bands == result.risk_bands.__class__(high=0, medium=0, low=0, unscored=0)


def test_summarize_ties_broken_deterministically_by_key() -> None:
    a = _row("BBB", blocker_count=30, reopen_rate=0.4, issue_aging_days=1000,
             critical_defect_ratio=0.3, open_issue_count=60)
    b = _row("AAA", blocker_count=30, reopen_rate=0.4, issue_aging_days=1000,
             critical_defect_ratio=0.3, open_issue_count=60)
    # identical scores -> project_key ascending breaks the tie
    result = _service([a, b], total_projects=2).summarize(top=2)
    assert [p.project_key for p in result.top_projects] == ["AAA", "BBB"]


# --- portfolio_score roll-up ----------------------------------------------- #
def test_portfolio_score_empty_is_zero() -> None:
    assert portfolio_score([]) == 0.0


def test_portfolio_score_bounded_and_severity_weighted() -> None:
    # 0.6*max + 0.4*severity_weighted_mean, both terms in [0,100] -> bounded.
    solo_high = portfolio_score([(90.0, "High"), (10.0, "Low"), (10.0, "Low")])
    many_high = portfolio_score([(90.0, "High"), (90.0, "High"), (90.0, "High")])
    assert 0.0 <= solo_high <= 100.0
    assert 0.0 <= many_high <= 100.0
    # a portfolio of all-High dominates one with a single High outlier
    assert many_high > solo_high
    # all-High collapses to the score itself (max==mean==90)
    assert many_high == 90.0


def test_summarize_populates_score_scope_and_computed_at() -> None:
    result = _service([HIGH, MID, LOW], total_projects=3).summarize(top=15)
    assert 0.0 <= result.portfolio_score <= 100.0
    assert result.portfolio_score > 0.0            # HIGH present -> non-zero
    assert result.scope.scoped is False            # no user_key -> unscoped
    assert result.scope.user_key is None
    assert result.scope.project_count == 3
    assert isinstance(result.computed_at, str) and result.computed_at


def test_summarize_scoped_narrows_to_project_keys_in_db() -> None:
    # Only MID/LOW are in the caller's assignment set -> HIGH must not appear,
    # totals + bands + score reflect only the scoped subset.
    result = _service([HIGH, MID, LOW], total_projects=3, total_issues=300).summarize(
        top=15, project_keys=["MID", "LOW"], user_key="mgr-x", scoped=True)

    keys = [p.project_key for p in result.top_projects]
    assert keys == ["MID", "LOW"]
    assert "HIGH" not in keys
    assert result.scope.scoped is True
    assert result.scope.user_key == "mgr-x"
    assert result.scope.project_count == 2         # scoped totals (2 projects)
    assert result.totals.projects == 2
    assert result.risk_bands.high == 0             # HIGH excluded
    assert result.risk_bands.unscored == 0


# --- as_of point-in-time view --------------------------------------------- #
def _as_of_service(scored, total_projects, snapshot_dates, total_issues=0, total_open=0):
    agg = PortfolioAggregate(
        total_projects=total_projects, total_issues=total_issues,
        total_open_issues=total_open, scored=scored,
    )
    return DefaultPortfolioSummaryService(
        FakePortfolioSummaryDao(agg, snapshot_dates=snapshot_dates)
    )


def test_summarize_as_of_none_is_unchanged_and_echoes_null() -> None:
    result = _service([HIGH, MID, LOW], total_projects=3).summarize(top=15)
    assert result.as_of is None
    assert [p.project_key for p in result.top_projects] == ["HIGH", "MID", "LOW"]


def test_summarize_as_of_narrows_to_snapshots_on_or_before_date() -> None:
    # HIGH snapshot is AFTER the as_of date -> excluded (unscored); MID/LOW stay.
    snapshots = {
        "HIGH": date(2026, 7, 10),
        "MID": date(2026, 7, 1),
        "LOW": date(2026, 6, 15),
    }
    result = _as_of_service(
        [HIGH, MID, LOW], total_projects=3, snapshot_dates=snapshots
    ).summarize(top=15, as_of=date(2026, 7, 5))

    keys = [p.project_key for p in result.top_projects]
    assert keys == ["MID", "LOW"]                  # HIGH's snapshot is too recent
    assert "HIGH" not in keys
    assert result.as_of == "2026-07-05"            # echoed back as ISO string
    assert result.risk_bands.high == 0             # HIGH dropped out
    assert result.risk_bands.unscored == 1         # 3 total - 2 scored as-of


def test_summarize_as_of_before_all_snapshots_is_all_unscored() -> None:
    snapshots = {"HIGH": date(2026, 7, 10), "MID": date(2026, 7, 1)}
    result = _as_of_service(
        [HIGH, MID], total_projects=2, snapshot_dates=snapshots
    ).summarize(top=15, as_of=date(2026, 1, 1))
    assert result.top_projects == []
    assert result.risk_bands.unscored == 2
    assert result.overall_risk == "Low"
    assert result.as_of == "2026-01-01"


def test_summarize_as_of_threads_to_dao() -> None:
    agg = PortfolioAggregate(
        total_projects=1, total_issues=0, total_open_issues=0, scored=[HIGH],
    )
    dao = FakePortfolioSummaryDao(agg, snapshot_dates={"HIGH": date(2026, 1, 1)})
    DefaultPortfolioSummaryService(dao).summarize(top=5, as_of=date(2026, 7, 5))
    assert dao.last_as_of == date(2026, 7, 5)


def test_summarize_as_of_and_scoping_apply_together() -> None:
    # Scope to MID/LOW; as_of excludes MID's too-recent snapshot -> only LOW.
    snapshots = {
        "HIGH": date(2026, 7, 1),
        "MID": date(2026, 7, 10),
        "LOW": date(2026, 6, 1),
    }
    result = _as_of_service(
        [HIGH, MID, LOW], total_projects=3, snapshot_dates=snapshots
    ).summarize(
        top=15, project_keys=["MID", "LOW"], user_key="mgr-x", scoped=True,
        as_of=date(2026, 7, 5),
    )
    keys = [p.project_key for p in result.top_projects]
    assert keys == ["LOW"]                          # HIGH out of scope, MID too recent
    assert result.scope.scoped is True
    assert result.as_of == "2026-07-05"
    assert result.scope.project_count == 2          # scoped totals unaffected by as_of
    assert result.risk_bands.unscored == 1          # 2 scoped - 1 as-of scored
