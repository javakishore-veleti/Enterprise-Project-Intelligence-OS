"""Real Airflow REST trigger for the dataset-acquisition DAG.

Dependency-free (stdlib urllib) so the Ingestion API keeps a small footprint.
POSTs to ``/api/v1/dags/{dag_id}/dagRuns`` with HTTP basic auth. If Airflow is
unreachable, raises DependencyUnavailableError so the caller surfaces a 503.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from ingestion_api.common.configuration import Settings
from ingestion_api.common.exceptions import DependencyUnavailableError
from ingestion_api.common.logging import get_logger
from ingestion_api.interfaces.daos import DatasetAcquisitionGateway

_logger = get_logger(__name__)


class AirflowDatasetAcquisitionGateway(DatasetAcquisitionGateway):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def trigger_acquire(self, dataset_id: str) -> str:
        s = self._settings
        url = f"{s.airflow_base_url.rstrip('/')}/api/v1/dags/{s.acquire_dag_id}/dagRuns"
        payload = json.dumps({"conf": {"dataset_id": dataset_id}}).encode()
        token = base64.b64encode(f"{s.airflow_user}:{s.airflow_password}".encode()).decode()
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
                f"Airflow rejected the acquire trigger ({exc.code}): {detail}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise DependencyUnavailableError(
                f"Airflow unreachable at {s.airflow_base_url} — is it running "
                f"(WITH_AIRFLOW=1)? {exc}"
            ) from exc
        dag_run_id = body.get("dag_run_id", f"{s.acquire_dag_id}:{dataset_id}")
        _logger.info("airflow acquire triggered", extra={"context": {
            "dag_id": s.acquire_dag_id, "dataset_id": dataset_id, "dag_run_id": dag_run_id}})
        return dag_run_id
