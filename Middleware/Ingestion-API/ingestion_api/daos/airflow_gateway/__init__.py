"""Gateway to Apache Airflow (operational workflow scheduler).

Foundation-slice implementation: records the trigger intent and returns a
synthetic external reference instead of calling the Airflow REST API. Swapping
in a real HTTP client is confined to this class — callers depend only on the
``AirflowGateway`` interface.
"""
from __future__ import annotations

from ingestion_api.common.configuration import Settings
from ingestion_api.common.logging import get_logger
from ingestion_api.interfaces.daos import AirflowGateway

_logger = get_logger(__name__)


class HttpAirflowGateway(AirflowGateway):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def trigger_ingestion(self, run_id: str, dataset_id: str) -> str:
        external_ref = f"dag:project_dataset_ingest:{run_id}"
        _logger.info(
            "airflow ingestion trigger requested",
            extra={"context": {
                "run_id": run_id,
                "dataset_id": dataset_id,
                "airflow_base_url": self._settings.airflow_base_url,
                "external_ref": external_ref,
            }},
        )
        # TODO(risk-analytics phase): POST to {airflow_base_url}/api/v1/dags/
        #   project_dataset_ingest/dagRuns with a conf carrying run_id/dataset_id.
        return external_ref
