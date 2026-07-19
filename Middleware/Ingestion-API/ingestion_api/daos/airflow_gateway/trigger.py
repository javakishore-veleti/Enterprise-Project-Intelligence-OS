"""Shared Airflow REST DAG-trigger helper (stdlib urllib, no extra deps)."""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from ingestion_api.common.configuration import Settings
from ingestion_api.common.exceptions import DependencyUnavailableError
from ingestion_api.common.logging import get_logger

_logger = get_logger(__name__)


def trigger_dag(settings: Settings, dag_id: str, conf: dict) -> str:
    """POST a dagRun to Airflow's REST API. Returns the dag_run id.

    Raises DependencyUnavailableError (-> HTTP 503) if Airflow is unreachable or
    rejects the request, so callers surface a clean "is Airflow running?" error.
    """
    url = f"{settings.airflow_base_url.rstrip('/')}/api/v1/dags/{dag_id}/dagRuns"
    payload = json.dumps({"conf": conf}).encode()
    token = base64.b64encode(
        f"{settings.airflow_user}:{settings.airflow_password}".encode()
    ).decode()
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Basic {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        raise DependencyUnavailableError(
            f"Airflow rejected the {dag_id} trigger ({exc.code}): {detail}"
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise DependencyUnavailableError(
            f"Airflow unreachable at {settings.airflow_base_url} — is it running "
            f"(WITH_AIRFLOW=1)? {exc}"
        ) from exc
    dag_run_id = body.get("dag_run_id", f"{dag_id}:{conf}")
    _logger.info("airflow dag triggered", extra={"context": {"dag_id": dag_id, "dag_run_id": dag_run_id}})
    return dag_run_id
