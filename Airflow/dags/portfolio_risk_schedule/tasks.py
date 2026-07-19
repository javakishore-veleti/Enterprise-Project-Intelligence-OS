"""Pure, importable task callables for the scheduled portfolio-level risk DAG.

These functions contain the operational logic and are deliberately kept free of
Airflow imports so they can be unit-tested in isolation with a *fake* HTTP
client (no network, no scheduler, no live RiskAnalytics-API).

The contract for the injected ``http`` client mirrors the ``requests`` module:
it must expose ``post(url, json=..., timeout=...)`` returning a response object
with ``raise_for_status()`` and ``json()``.

Airflow owns *operational* work only: these callables trigger portfolio-level
(cross-project) risk analysis through the RiskAnalytics-API FastAPI boundary.
They never touch a database directly and contain **no** agent/LLM/reasoning
logic — the portfolio orchestrator and its agents live behind the
FastAPI/LangGraph boundary.

Endpoint status: the portfolio analysis endpoint is **PLANNED / NOT YET
IMPLEMENTED** in the RiskAnalytics-API. Only the per-project endpoint
(``POST /api/v1/analysis/projects/{project_key}``) exists today. The
``POST /api/v1/analysis/portfolios/{portfolio_key}`` call modelled below is the
*intended* contract (mirroring the per-project body
``{"agents": [...], "requested_by": "airflow"}``) and is documented in-line.
The middleware README/roadmap tracks this as the planned
``portfolio_risk_orchestrator`` graph in ``RiskAnalytics-API/graphs/``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Protocol

DEFAULT_BASE_URL = "http://localhost:8004"
DEFAULT_TIMEOUT = 600  # a portfolio fan-out spans many projects and can be slow

# Endpoint — the RiskAnalytics-API portfolio contract (now built).
ANALYSIS_PORTFOLIOS_PATH = "/api/v1/analysis/portfolios"


class HttpClient(Protocol):
    """Minimal HTTP surface used by the task callables (satisfied by ``requests``)."""

    def post(self, url: str, json: Dict[str, Any], timeout: int) -> Any:  # noqa: A002
        ...


def get_base_url() -> str:
    """Resolve the RiskAnalytics-API base URL from the environment.

    Falls back to :data:`DEFAULT_BASE_URL` so DAG parsing never fails on a
    missing variable.
    """
    return os.environ.get("RISK_ANALYTICS_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def build_portfolio_request(
    portfolio_key: str,
    agents: List[str],
    requested_by: str = "airflow",
) -> Dict[str, Any]:
    """Assemble and validate the portfolio analysis request (a pure shaping step).

    Raises ``ValueError`` when ``portfolio_key`` or ``requested_by`` is missing,
    so a misconfigured schedule fails fast before any HTTP call is made.
    """
    if not portfolio_key or not str(portfolio_key).strip():
        raise ValueError("portfolio_key is required")
    if not requested_by:
        raise ValueError("requested_by is required")

    return {
        "portfolio_key": str(portfolio_key).strip(),
        "agents": list(agents),
        "requested_by": requested_by,
    }


def start_portfolio_analysis(
    base_url: str,
    http: HttpClient,
    request: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """POST a portfolio analysis run and return a compact result summary.

    NOTE: ``POST /api/v1/analysis/portfolios/{portfolio_key}`` is not yet
    implemented in the RiskAnalytics-API. Modelled against the intended contract
    (body ``{"agents": [...], "requested_by": ...}``, mirroring the per-project
    endpoint). Raises ``RuntimeError`` if the response lacks a ``run_id``.
    """
    portfolio_key = request["portfolio_key"]
    url = f"{base_url.rstrip('/')}{ANALYSIS_PORTFOLIOS_PATH}/{portfolio_key}"
    body = {
        "agents": list(request.get("agents", [])),
        "requested_by": request.get("requested_by", "airflow"),
    }
    response = http.post(url, json=body, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    run_id = payload.get("run_id")
    if not run_id:
        raise RuntimeError(
            f"RiskAnalytics-API did not return a run_id for portfolio "
            f"{portfolio_key}: {payload!r}"
        )

    return {
        "portfolio_key": payload.get("portfolio_key", portfolio_key),
        "run_id": run_id,
        "status": payload.get("status", "RUNNING"),
        "finding_count": len(payload.get("findings", [])),
        "project_count": payload.get("project_count"),
    }


def finalize(result: Dict[str, Any]) -> Dict[str, Any]:
    """Interpret the portfolio run result and fail the DAG on a bad outcome.

    Returns a compact summary when the run COMPLETED; raises ``RuntimeError``
    otherwise so the scheduled DAG surfaces a red run.
    """
    status = result.get("status")
    portfolio_key = result.get("portfolio_key")

    if status == "COMPLETED":
        return {
            "portfolio_key": portfolio_key,
            "run_id": result.get("run_id"),
            "status": status,
            "finding_count": result.get("finding_count"),
            "ok": True,
        }

    raise RuntimeError(
        f"Portfolio analysis for {portfolio_key} finished with non-success "
        f"status {status!r}"
    )
