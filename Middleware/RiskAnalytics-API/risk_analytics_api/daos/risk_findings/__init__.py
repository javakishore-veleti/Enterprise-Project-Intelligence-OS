"""PostgreSQL-backed persistence of risk findings."""
from __future__ import annotations

import json

from agent_core import RiskFinding

from risk_analytics_api.common.utilities import new_id
from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.responses import RiskFindingResponse
from risk_analytics_api.interfaces.daos import RiskFindingDao

_COLUMNS = (
    "finding_id, run_id, project_key, agent_key, risk_category, probability, impact, "
    "severity, score, confidence, explanation, assumptions, recommended_actions, "
    "affected, analysis_timestamp, meta"
)


def _to_response(r: tuple) -> RiskFindingResponse:
    def _jsonlist(v):
        if isinstance(v, str):
            v = json.loads(v)
        return list(v or [])

    def _jsonobj(v):
        if isinstance(v, str):
            v = json.loads(v)
        return dict(v or {})

    return RiskFindingResponse(
        finding_id=r[0],
        agent_key=r[3],
        risk_category=r[4],
        probability=r[5],
        impact=r[6],
        severity=r[7],
        score=r[8],
        confidence=r[9],
        explanation=r[10],
        assumptions=_jsonlist(r[11]),
        recommended_actions=_jsonlist(r[12]),
        affected=_jsonlist(r[13]),
        analysis_timestamp=r[14],
        meta=_jsonobj(r[15]),
    )


class PostgresRiskFindingDao(RiskFindingDao):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def add_many(self, run_id, project_key, findings: list[RiskFinding]) -> list[str]:
        ids: list[str] = []
        with self._db.connection() as conn:
            cur = conn.cursor()
            for f in findings:
                fid = new_id()
                ids.append(fid)
                cur.execute(
                    f"INSERT INTO risk.risk_findings ({_COLUMNS}) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb)",
                    (
                        fid, run_id, project_key, f.source_agent, f.risk_category.value,
                        f.probability, f.impact, f.severity.value, f.score, f.confidence,
                        f.explanation, json.dumps(f.assumptions), json.dumps(f.recommended_actions),
                        json.dumps(f.affected), f.analysis_timestamp, json.dumps(f.meta),
                    ),
                )
        return ids

    def list_for_run(self, run_id: str) -> list[RiskFindingResponse]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM risk.risk_findings WHERE run_id = %s "
                "ORDER BY score DESC, finding_id",
                (run_id,),
            )
            return [_to_response(r) for r in cur.fetchall()]
