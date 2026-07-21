"""Airflow REST triggers for the dataset acquire + ingest DAGs."""
from __future__ import annotations

from ingestion_api.common.configuration import Settings
from ingestion_api.daos.airflow_gateway.trigger import trigger_dag
from ingestion_api.interfaces.daos import (
    DatasetAcquisitionGateway,
    DatasetIngestionGateway,
    MetricsComputeGateway,
)


class AirflowDatasetAcquisitionGateway(DatasetAcquisitionGateway):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def trigger_acquire(self, dataset_id: str) -> str:
        return trigger_dag(self._settings, self._settings.acquire_dag_id, {"dataset_id": dataset_id})


class AirflowDatasetIngestionGateway(DatasetIngestionGateway):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def trigger_ingest(self, dataset_id: str, run_id: str, repos: list[str] | None = None) -> str:
        conf = {"dataset_id": dataset_id, "run_id": run_id}
        if repos:
            conf["repos"] = repos
        return trigger_dag(self._settings, self._settings.ingest_dag_id, conf)


class AirflowMetricsComputeGateway(MetricsComputeGateway):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def trigger_compute(self) -> str:
        return trigger_dag(self._settings, self._settings.metrics_dag_id, {})
