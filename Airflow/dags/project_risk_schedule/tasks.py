"""Pure, importable task callables for the scheduled per-project risk DAG.

These functions contain the operational logic and are deliberately kept free of
Airflow imports so they can be unit-tested in isolation with a *fake* HTTP
client (no network, no scheduler, no live RiskAnalytics-API).

The contract for the injected ``http`` client mirrors the ``requests`` module:
it must expose ``post(url, json=..., timeout=...)`` returning a response object
with ``raise_for_status()`` and ``json()``.

Airflow owns *operational* work only: these callables trigger multi-agent risk
analysis through the RiskAnalytics-API FastAPI boundary. They never touch a
database directly and contain **no** agent/LLM/reasoning logic — the agents and
their prompts live behind the FastAPI/LangGraph boundary.

Endpoint status: ``POST /api/v1/analysis/projects/{project_key}`` EXISTS in the
RiskAnalytics-API today (returns ``AnalysisRunResponse`` synchronously with a
terminal status of ``COMPLETED``/``FAILED``/``RUNNING``). This DAG models it
accurately: request body ``{"agents": [...], "requested_by": "airflow"}``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Protocol

DEFAULT_BASE_URL = "http://localhost:8004"
DEFAULT_TIMEOUT = 300  # analysis is synchronous and can take a while

ANALYSIS_PROJECTS_PATH = "/api/v1/analysis/projects"

# A terminal analysis run is one whose work finished; only COMPLETED counts as OK.
TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED"})


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


def resolve_projects(project_keys: List[str]) -> List[str]:
    """Validate and normalise the configured set of project keys (pure step).

    Raises ``ValueError`` when the configured list is empty or contains blanks,
    so a misconfigured schedule fails fast before any HTTP call is made.
    """
    if not project_keys:
        raise ValueError("project_keys must be a non-empty list")

    normalised: List[str] = []
    for key in project_keys:
        if not key or not str(key).strip():
            raise ValueError(f"invalid project key in configured set: {key!r}")
        normalised.append(str(key).strip())
    return normalised


def start_project_analysis(
    base_url: str,
    http: HttpClient,
    project_key: str,
    agents: List[str],
    requested_by: str = "airflow",
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """POST a project analysis run and return a compact result summary.

    Calls the existing RiskAnalytics-API endpoint
    ``POST /api/v1/analysis/projects/{project_key}`` with body
    ``{"agents": [...], "requested_by": ...}``. Raises ``RuntimeError`` if the
    response lacks a ``run_id``.
    """
    if not project_key:
        raise ValueError("project_key is required")

    url = f"{base_url.rstrip('/')}{ANALYSIS_PROJECTS_PATH}/{project_key}"
    body = {"agents": list(agents), "requested_by": requested_by}
    response = http.post(url, json=body, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    run_id = payload.get("run_id")
    if not run_id:
        raise RuntimeError(
            f"RiskAnalytics-API did not return a run_id for {project_key}: {payload!r}"
        )

    return {
        "project_key": payload.get("project_key", project_key),
        "run_id": run_id,
        "status": payload.get("status", "RUNNING"),
        "finding_count": len(payload.get("findings", [])),
    }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-project results and fail the DAG if any run did not complete.

    Returns counts of completed vs failed runs. Raises ``RuntimeError`` when one
    or more scheduled analyses did not reach ``COMPLETED`` so the scheduled DAG
    surfaces a red run.
    """
    results = list(results)
    completed = [r for r in results if r.get("status") == "COMPLETED"]
    not_completed = [r for r in results if r.get("status") != "COMPLETED"]

    summary = {
        "total": len(results),
        "completed": len(completed),
        "failed": len(not_completed),
        "total_findings": sum(int(r.get("finding_count", 0)) for r in results),
        "projects": [r.get("project_key") for r in results],
    }

    if not_completed:
        failed_keys = [r.get("project_key") for r in not_completed]
        raise RuntimeError(
            f"{len(not_completed)} scheduled project analyses did not complete: "
            f"{failed_keys!r} (summary: {summary!r})"
        )
    return summary
