"""PostgreSQL-backed persistence of generated review reports."""
from __future__ import annotations

import json

from agent_core import RiskReport

from risk_analytics_api.common.utilities import new_id
from risk_analytics_api.daos.connection import PostgresDatabase
from risk_analytics_api.dtos.responses import ReportResponse
from risk_analytics_api.interfaces.daos import ReportDao

_COLUMNS = "report_id, run_id, project_key, kind, title, summary, sections, source_agent, generated_at"


def _to_response(r: tuple) -> ReportResponse:
    sections = r[6]
    if isinstance(sections, str):
        sections = json.loads(sections)
    return ReportResponse(
        report_id=r[0],
        kind=r[3],
        title=r[4],
        summary=r[5],
        sections=list(sections or []),
        source_agent=r[7],
        generated_at=r[8],
    )


class PostgresReportDao(ReportDao):
    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def add_many(self, run_id: str, project_key: str, reports: list[RiskReport]) -> list[str]:
        ids: list[str] = []
        with self._db.connection() as conn:
            cur = conn.cursor()
            for rep in reports:
                rid = new_id()
                ids.append(rid)
                cur.execute(
                    f"INSERT INTO risk.reports ({_COLUMNS}) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                    (
                        rid, run_id, project_key, rep.kind.value, rep.title, rep.summary,
                        json.dumps(rep.sections), rep.source_agent, rep.generated_at,
                    ),
                )
        return ids

    def list_for_run(self, run_id: str) -> list[ReportResponse]:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM risk.reports WHERE run_id = %s ORDER BY kind",
                (run_id,),
            )
            return [_to_response(r) for r in cur.fetchall()]
