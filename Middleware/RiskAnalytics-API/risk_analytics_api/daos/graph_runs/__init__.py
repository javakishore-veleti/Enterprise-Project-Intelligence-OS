"""PostgreSQL-backed persistence of analysis (graph) runs."""
from __future__ import annotations

import json

from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.responses import AnalysisRunResponse
from risk_analytics_api.interfaces.daos import RiskFindingDao
from risk_analytics_api.interfaces.daos import GraphRunDao


class PostgresGraphRunDao(GraphRunDao):
    def __init__(self, database: PostgresDatabase, findings_dao: RiskFindingDao) -> None:
        self._db = database
        self._findings = findings_dao

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
        )
