"""PostgreSQL-backed persistence of analysis (graph) runs."""
from __future__ import annotations

import json

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.responses import AnalysisRunResponse, AnalysisRunSummary
from risk_analytics_api.interfaces.daos import GraphRunDao, ReportDao, RiskFindingDao


class PostgresGraphRunDao(GraphRunDao):
    def __init__(
        self, database: PostgresDatabase, findings_dao: RiskFindingDao, reports_dao: ReportDao
    ) -> None:
        self._db = database
        self._findings = findings_dao
        self._reports = reports_dao

    def create(self, run_id, project_key, agent_keys, started_at) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO risk.graph_runs (run_id, project_key, status, agent_keys, started_at) "
                "VALUES (%s, %s, %s, %s::jsonb, %s)",
                (run_id, project_key, AnalysisStatus.RUNNING.value, json.dumps(agent_keys), started_at),
            )

    def complete(self, run_id, status, finished_at) -> None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE risk.graph_runs SET status = %s, finished_at = %s WHERE run_id = %s",
                (status, finished_at, run_id),
            )

    def get(self, run_id: str) -> AnalysisRunResponse | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT run_id, project_key, status, agent_keys, started_at, finished_at "
                "FROM risk.graph_runs WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        agent_keys = row[3]
        if isinstance(agent_keys, str):
            agent_keys = json.loads(agent_keys)
        return AnalysisRunResponse(
            run_id=row[0],
            project_key=row[1],
            status=AnalysisStatus(row[2]),
            agent_keys=list(agent_keys or []),
            started_at=row[4],
            finished_at=row[5],
            findings=self._findings.list_for_run(run_id),
            reports=self._reports.list_for_run(run_id),
        )

    def list_for_project(self, project_key: str, limit: int) -> list[AnalysisRunSummary]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT g.run_id, g.project_key, g.status, g.agent_keys, g.started_at, g.finished_at, "
                "  (SELECT count(*) FROM risk.risk_findings f WHERE f.run_id = g.run_id), "
                "  (SELECT count(*) FROM risk.reports r WHERE r.run_id = g.run_id) "
                "FROM risk.graph_runs g WHERE g.project_key = %s "
                "ORDER BY g.started_at DESC LIMIT %s",
                (project_key, limit),
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
