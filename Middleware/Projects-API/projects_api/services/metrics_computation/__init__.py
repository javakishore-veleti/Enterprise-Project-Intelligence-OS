"""Deterministic project-metrics computation (no LLM).

Turns ingested evidence (issues / histories / links) into the observable facts
the detector agents consume — backlog growth, reopen rate, blocker count,
dependency depth — and upserts them into ``project_metrics``. Pure Python +
MongoDB queries; the derived math and the dependency-graph depth are separated
into testable helpers.
"""
from __future__ import annotations

from datetime import timedelta

from projects_api.common.exceptions import NotFoundError
from projects_api.common.utilities import utc_now
from projects_api.dtos.responses import ProjectMetricsResponse
from projects_api.interfaces.daos import MetricsComputationDao, ProjectsDao
from projects_api.interfaces.services import MetricsComputationService

WINDOW_DAYS = 30


def backlog_growth(created_in_window: int, resolved_in_window: int, open_issue_count: int) -> float:
    """Net new open work over the window, as a fraction of the current open backlog."""
    return round((created_in_window - resolved_in_window) / max(1, open_issue_count), 3)


def reopen_rate(reopened_count: int, resolved_count: int) -> float:
    return round(reopened_count / max(1, resolved_count), 3)


def dependency_depth(links: list[tuple[str, str]]) -> int:
    """Longest chain (node count) in the blocking/dependency graph. Cycle-safe."""
    adj: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for src, dst in links:
        adj.setdefault(src, []).append(dst)
        nodes.add(src)
        nodes.add(dst)
    if not nodes:
        return 0

    memo: dict[str, int] = {}

    def longest(node: str, on_path: set[str]) -> int:
        if node in on_path:  # cycle -> stop
            return 0
        if node in memo:
            return memo[node]
        on_path.add(node)
        best = 1 + max((longest(t, on_path) for t in adj.get(node, [])), default=0)
        on_path.discard(node)
        memo[node] = best
        return best

    return max(longest(n, set()) for n in nodes)


class DefaultMetricsComputationService(MetricsComputationService):
    def __init__(self, metrics_dao: MetricsComputationDao, projects_dao: ProjectsDao) -> None:
        self._dao = metrics_dao
        self._projects = projects_dao

    def compute(self, project_key: str) -> ProjectMetricsResponse:
        if self._projects.get(project_key) is None:
            raise NotFoundError(f"project '{project_key}' not found")

        c = self._dao.counts(project_key)
        reopened = self._dao.reopened_count(project_key)

        ref = self._dao.reference_date(project_key)
        if ref is not None:
            start = ref - timedelta(days=WINDOW_DAYS)
            prior_start = ref - timedelta(days=2 * WINDOW_DAYS)
            created_w = self._dao.created_between(project_key, start, ref)
            resolved_w = self._dao.resolved_between(project_key, start, ref)
            resolved_prior = self._dao.resolved_between(project_key, prior_start, start)
            growth = backlog_growth(created_w, resolved_w, c["open_issue_count"])
            aging = self._dao.avg_open_age_days(project_key, ref)
        else:
            growth = 0.0
            resolved_w = resolved_prior = 0
            aging = 0.0

        open_count = c["open_issue_count"]
        metrics = {
            "backlog_growth": growth,
            "reopen_rate": reopen_rate(reopened, c["resolved_count"]),
            "blocker_count": c["blocker_count"],
            "dependency_depth": dependency_depth(self._dao.blocking_links(project_key)),
            "issue_aging_days": aging,
            "resolution_velocity": float(resolved_w),
            "resolution_velocity_trend": float(resolved_w - resolved_prior),
            "contributor_concentration": self._dao.top_contributor_share(project_key),
            "critical_defect_ratio": round(self._dao.critical_open_count(project_key) / max(1, open_count), 3),
        }
        computed_at = utc_now()
        self._dao.write_metrics(project_key, metrics, computed_at)
        self._dao.update_project_counts(project_key, c["issue_count"], c["open_issue_count"])
        return ProjectMetricsResponse(project_key=project_key, computed_at=computed_at, **metrics)

    def compute_all(self, limit: int) -> list[str]:
        keys = self._dao.list_project_keys(limit)
        for key in keys:
            self.compute(key)
        return keys
