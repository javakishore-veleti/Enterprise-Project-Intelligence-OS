"""Unit tests for the Investigation Agent evidence tools (fake Mongo, no infra).

Each tool is a pure function of (db, project_key, params). These assert the
bounded evidence contract: correct counts, capped samples, and project scoping.
"""
from __future__ import annotations

from risk_analytics_api.graphs.investigation.tools import (
    MAX_SAMPLE,
    aging_issues,
    blocker_issues,
    contributor_breakdown,
    dependency_links,
    metrics_snapshot,
    reopened_issues,
    status_change_timeline,
)
from tests.support.mongo import FakeMongo

COLLECTIONS = {
    "projects": [
        {"project_key": "APACHE", "name": "Apache", "issue_count": 10, "open_issue_count": 6},
    ],
    "project_metrics": [
        {"project_key": "APACHE", "computed_at": "2026-01-01", "blocker_count": 2,
         "reopen_rate": 0.3, "issue_aging_days": 120.0, "resolution_velocity": 5.0,
         "resolution_velocity_trend": -2.0, "contributor_concentration": 0.57,
         "dependency_depth": 2, "critical_defect_ratio": 0.33, "backlog_growth": 0.1},
        {"project_key": "APACHE", "computed_at": "2026-02-01", "blocker_count": 9,
         "reopen_rate": 0.4, "issue_aging_days": 130.0, "resolution_velocity": 4.0,
         "resolution_velocity_trend": -3.0, "contributor_concentration": 0.6,
         "dependency_depth": 3, "critical_defect_ratio": 0.4, "backlog_growth": 0.2},
    ],
    "issue_histories": [
        {"issue_key": "A-1", "project_key": "APACHE", "field": "status",
         "to_value": "Reopened", "changed_at": "2026-01-05", "author": "alice"},
        {"issue_key": "A-1", "project_key": "APACHE", "field": "status",
         "to_value": "In Progress", "changed_at": "2026-01-06", "author": "alice"},
        {"issue_key": "A-2", "project_key": "APACHE", "field": "status",
         "to_value": "Open", "changed_at": "2026-01-07", "author": "bob"},
        {"issue_key": "A-3", "project_key": "APACHE", "field": "status",
         "to_value": "Reopen", "changed_at": "2026-01-08", "author": "alice"},
        {"issue_key": "A-4", "project_key": "APACHE", "field": "priority",
         "to_value": "Blocker", "changed_at": "2026-01-09", "author": "carol"},
        {"issue_key": "X-1", "project_key": "OTHER", "field": "status",
         "to_value": "Reopened", "changed_at": "2026-01-05", "author": "zed"},
    ],
    "issues": [
        {"issue_key": "A-10", "project_key": "APACHE", "status": "Open",
         "priority": "Blocker", "created_at": "2025-01-01"},
        {"issue_key": "A-11", "project_key": "APACHE", "status": "In Progress",
         "priority": "Critical", "created_at": "2025-06-01"},
        {"issue_key": "A-12", "project_key": "APACHE", "status": "Done",
         "priority": "Blocker", "created_at": "2025-02-01"},
        {"issue_key": "A-13", "project_key": "APACHE", "status": "Open",
         "priority": "Major", "created_at": "2025-03-01"},
        {"issue_key": "A-14", "project_key": "OTHER", "status": "Open",
         "priority": "Blocker", "created_at": "2025-01-01"},
    ],
    "issue_links": [
        {"source_issue_key": "A-1", "target_issue_key": "A-2", "link_type": "blocks",
         "project_key": "APACHE"},
        {"source_issue_key": "A-3", "target_issue_key": "A-4", "link_type": "depends on",
         "project_key": "APACHE"},
        {"source_issue_key": "A-5", "target_issue_key": "A-6", "link_type": "relates to",
         "project_key": "APACHE"},
        {"source_issue_key": "B-1", "target_issue_key": "B-2", "link_type": "blocks",
         "project_key": "OTHER"},
    ],
    "comments": [
        {"project_key": "APACHE", "author": "alice"},
        {"project_key": "APACHE", "author": "dave"},
    ],
}


def _db():
    return FakeMongo(COLLECTIONS).db()


def test_metrics_snapshot_returns_latest_by_computed_at() -> None:
    snap = metrics_snapshot(_db(), "APACHE")
    assert snap["computed_at"] == "2026-02-01"
    assert snap["metrics"]["blocker_count"] == 9  # latest snapshot, not the older 2
    assert snap["metrics"]["contributor_concentration"] == 0.6


def test_reopened_issues_counts_distinct_and_scopes_project() -> None:
    result = reopened_issues(_db(), "APACHE")
    assert result["count"] == 3  # A-1, A-2, A-3 (X-1 is a different project)
    assert all(row["issue_key"].startswith("A-") for row in result["sample"])


def test_reopened_issues_sample_bounded_by_limit() -> None:
    result = reopened_issues(_db(), "APACHE", limit=2)
    assert result["count"] == 3
    assert len(result["sample"]) == 2  # count unbounded, sample capped by limit


def test_blocker_issues_only_open_critical() -> None:
    result = blocker_issues(_db(), "APACHE")
    assert result["count"] == 2  # A-10 (Blocker/Open), A-11 (Critical/In Progress)
    keys = {row["issue_key"] for row in result["sample"]}
    assert keys == {"A-10", "A-11"}  # A-12 Done, A-13 Major, A-14 other project excluded


def test_aging_issues_open_only_oldest_first() -> None:
    result = aging_issues(_db(), "APACHE")
    assert result["count"] == 3  # A-10, A-11, A-13 (A-12 closed, A-14 other project)
    assert [row["issue_key"] for row in result["sample"]] == ["A-10", "A-13", "A-11"]


def test_dependency_links_blocking_only() -> None:
    result = dependency_links(_db(), "APACHE")
    assert result["count"] == 2  # blocks + depends on; "relates to" + other project excluded
    assert {row["link_type"] for row in result["sample"]} == {"blocks", "depends on"}


def test_contributor_breakdown_concentration_and_ordering() -> None:
    result = contributor_breakdown(_db(), "APACHE")
    # alice: 3 histories + 1 comment = 4; bob 1, carol 1, dave 1 -> total 7
    assert result["total_changes"] == 7
    assert result["top"][0] == {"author": "alice", "changes": 4}
    assert result["concentration"] == round(4 / 7, 3)


def test_status_change_timeline_recent_first() -> None:
    result = status_change_timeline(_db(), "APACHE")
    assert result["count"] == 4  # four status-field changes for APACHE
    assert result["sample"][0]["issue_key"] == "A-3"  # newest changed_at (2026-01-08)


def test_sample_is_hard_capped_at_max_sample() -> None:
    many = {"issue_histories": [
        {"issue_key": f"A-{i}", "project_key": "APACHE", "field": "status",
         "to_value": "In Progress", "changed_at": f"2026-01-{i:02d}", "author": "alice"}
        for i in range(1, 31)  # 30 status changes
    ]}
    db = FakeMongo(many).db()
    result = status_change_timeline(db, "APACHE", limit=100)
    assert result["count"] == 30
    assert len(result["sample"]) == MAX_SAMPLE  # bounded regardless of requested limit
