"""Builds a bounded evidence package from the MongoDB evidence store.

This is the deterministic boundary of the evidence-grounding invariant: it reads
project facts + computed metrics and phrases them as observations. No raw issue
records and no LLM are involved here.
"""
from __future__ import annotations

from agent_core import EvidenceMetrics, EvidencePackage

from risk_analytics_api.daos.connection import MongoDatabaseFactory
from risk_analytics_api.interfaces.daos import EvidenceDao


def _observations(name: str, m: EvidenceMetrics) -> list[str]:
    obs: list[str] = []
    if m.backlog_growth > 0:
        obs.append(f"Backlog grew {m.backlog_growth:.0%} month-over-month.")
    if m.reopen_rate > 0:
        obs.append(f"Reopen rate is {m.reopen_rate:.0%}, indicating rework churn.")
    if m.blocker_count:
        obs.append(f"{m.blocker_count} open blocker issue(s) currently constrain progress.")
    if m.dependency_depth:
        obs.append(f"Longest dependency chain is {m.dependency_depth} levels deep.")
    if m.issue_count:
        open_pct = (m.open_issue_count / m.issue_count) if m.issue_count else 0.0
        obs.append(
            f"{m.open_issue_count} of {m.issue_count} issues are open ({open_pct:.0%})."
        )
    if m.issue_aging_days:
        obs.append(f"Open issues average {m.issue_aging_days:.0f} days old.")
    if m.resolution_velocity:
        obs.append(f"Resolution velocity is {m.resolution_velocity:.0f} issues in the recent window.")
    if m.contributor_concentration:
        obs.append(
            f"Top contributor accounts for {m.contributor_concentration:.0%} of activity "
            "(resource/bus-factor concentration).")
    if m.critical_defect_ratio:
        obs.append(f"{m.critical_defect_ratio:.0%} of open issues are Blocker/Critical.")
    return obs


class MongoEvidenceDao(EvidenceDao):
    def __init__(self, mongo: MongoDatabaseFactory) -> None:
        self._mongo = mongo

    def build_package(self, project_key: str) -> EvidencePackage | None:
        db = self._mongo.db()
        project = db["projects"].find_one({"project_key": project_key}, {"_id": 0})
        if project is None:
            return None

        metrics_doc = db["project_metrics"].find_one(
            {"project_key": project_key}, sort=[("computed_at", -1)]
        ) or {}

        metrics = EvidenceMetrics(
            backlog_growth=float(metrics_doc.get("backlog_growth", 0.0)),
            reopen_rate=float(metrics_doc.get("reopen_rate", 0.0)),
            blocker_count=int(metrics_doc.get("blocker_count", 0)),
            dependency_depth=int(metrics_doc.get("dependency_depth", 0)),
            issue_count=int(project.get("issue_count", 0)),
            open_issue_count=int(project.get("open_issue_count", 0)),
            issue_aging_days=float(metrics_doc.get("issue_aging_days", 0.0)),
            resolution_velocity=float(metrics_doc.get("resolution_velocity", 0.0)),
            contributor_concentration=float(metrics_doc.get("contributor_concentration", 0.0)),
            critical_defect_ratio=float(metrics_doc.get("critical_defect_ratio", 0.0)),
        )
        name = project.get("name", project_key)
        return EvidencePackage(
            project_key=project_key,
            project_name=name,
            metrics=metrics,
            observations=_observations(name, metrics),
        )

    def list_project_keys(self, limit: int) -> list[str]:
        cursor = (
            self._mongo.db()["projects"]
            .find({}, {"_id": 0, "project_key": 1})
            .sort("project_key", 1)
            .limit(limit)
        )
        return [d["project_key"] for d in cursor if d.get("project_key")]
