"""PostgreSQL-backed cross-project reads for the dashboard activity feed."""
from __future__ import annotations

import json

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.responses import (
    AnalysisRunSummary,
    DashboardFindingSummary,
    DashboardTotals,
)
from risk_analytics_api.interfaces.daos import DashboardDao

#: Cap on the finding explanation surfaced in the activity feed.
_EXPLANATION_MAX = 240


class PostgresDashboardDao(DashboardDao):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def recent_runs(self, limit: int) -> list[AnalysisRunSummary]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT g.run_id, g.project_key, g.status, g.agent_keys, g.started_at, g.finished_at, "
                "  (SELECT count(*) FROM risk.risk_findings f WHERE f.run_id = g.run_id), "
                "  (SELECT count(*) FROM risk.reports r WHERE r.run_id = g.run_id) "
                "FROM risk.graph_runs g "
                "ORDER BY g.started_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        summaries = []
        for r in rows:
            agent_keys = r[3]
            if isinstance(agent_keys, str):
                agent_keys = json.loads(agent_keys)
            summaries.append(AnalysisRunSummary(
                run_id=r[0], project_key=r[1], status=AnalysisStatus(r[2]),
                agent_keys=list(agent_keys or []), started_at=r[4], finished_at=r[5],
                finding_count=r[6], report_count=r[7]))
        return summaries

    def recent_findings(self, limit: int) -> list[DashboardFindingSummary]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT finding_id, run_id, project_key, agent_key, risk_category, severity, "
                "  score, explanation "
                "FROM risk.risk_findings "
                "ORDER BY analysis_timestamp DESC, finding_id LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        return [
            DashboardFindingSummary(
                finding_id=r[0], run_id=r[1], project_key=r[2], agent_key=r[3],
                risk_category=r[4], severity=r[5], score=r[6],
                explanation=(r[7] or "")[:_EXPLANATION_MAX],
            )
            for r in rows
        ]

    def totals(self) -> DashboardTotals:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT (SELECT count(*) FROM risk.graph_runs), "
                "  (SELECT count(*) FROM risk.risk_findings), "
                "  (SELECT count(DISTINCT project_key) FROM risk.graph_runs)"
            )
            row = cur.fetchone()
        return DashboardTotals(
            total_runs=row[0], total_findings=row[1], projects_analyzed=row[2])
