"""Airflow DAG: scheduled portfolio-level risk analysis.

Task flow::

    build_portfolio_request -> start_portfolio_analysis -> finalize

The DAG is a thin operational wrapper: every task delegates to a pure callable
in :mod:`tasks`, injecting ``requests`` as the HTTP client and the
RiskAnalytics-API base URL from the ``RISK_ANALYTICS_API_BASE_URL`` env var. No
database access and no agent/LLM logic live here — analysis is driven
exclusively through the RiskAnalytics-API FastAPI boundary, which owns the
LangGraph orchestration.

NOTE: the portfolio analysis endpoint is *planned* and **not yet implemented**
in the RiskAnalytics-API (only the per-project endpoint exists today). This DAG
models the intended call; see ``tasks.py`` PENDING markers.

Runs on a weekly cron schedule.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow.decorators import dag, task

from portfolio_risk_schedule import tasks

DEFAULT_ARGS = {
    "owner": "risk-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}

DEFAULT_PARAMS = {
    "portfolio_key": "ALL",
    # Agent keys to run; empty means the middleware runs its configured default set.
    "agents": [],
    "requested_by": "airflow",
}


@dag(
    dag_id="portfolio_risk_schedule",
    description="Scheduled portfolio-level risk analysis via the RiskAnalytics-API (endpoint pending).",
    schedule="0 7 * * 1",  # weekly, Mondays at 07:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params=DEFAULT_PARAMS,
    tags=["risk", "scheduled", "portfolio"],
    doc_md=__doc__,
)
def portfolio_risk_schedule():
    @task
    def build_portfolio_request(**context):
        params = context["params"]
        return tasks.build_portfolio_request(
            portfolio_key=params["portfolio_key"],
            agents=params["agents"],
            requested_by=params["requested_by"],
        )

    @task
    def start_portfolio_analysis(request):
        return tasks.start_portfolio_analysis(
            base_url=tasks.get_base_url(),
            http=requests,
            request=request,
        )

    @task
    def finalize(result):
        return tasks.finalize(result)

    request = build_portfolio_request()
    result = start_portfolio_analysis(request)
    finalize(result)


dag = portfolio_risk_schedule()
