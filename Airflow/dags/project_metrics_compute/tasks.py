"""Pure task callables for the project-metrics compute DAG.

Airflow-free so they unit-test with a fake HTTP client. The DAG recomputes
deterministic project metrics from ingested evidence by calling the Projects-API
(which owns the computation); it holds no metric logic itself.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Protocol

DEFAULT_BASE_URL = "http://localhost:8003"
DEFAULT_TIMEOUT = 120


class HttpClient(Protocol):
    def get(self, url: str, timeout: int = ...) -> Any: ...
    def post(self, url: str, timeout: int = ...) -> Any: ...


def get_base_url() -> str:
    return (os.environ.get("PROJECTS_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def list_project_keys(base_url: str, http: HttpClient, page_size: int = 200) -> List[str]:
    """All project keys, paginated (the list endpoint caps ``limit`` at 200)."""
    keys: List[str] = []
    offset = 0
    while True:
        resp = http.get(
            f"{base_url}/api/v1/projects?limit={page_size}&offset={offset}", timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        keys.extend(p["project_key"] for p in items)
        if len(items) < page_size:
            break
        offset += page_size
    return keys


def compute_project(base_url: str, http: HttpClient, project_key: str) -> Dict[str, Any]:
    resp = http.post(
        f"{base_url}/api/v1/projects/{project_key}/metrics/compute", timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()
