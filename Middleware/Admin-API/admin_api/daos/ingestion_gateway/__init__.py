"""HTTP gateway to the Ingestion API for dataset acquisition (stdlib urllib)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from admin_api.common.configuration import Settings
from admin_api.common.exceptions import DependencyUnavailableError
from admin_api.dtos.dataset import DatasetStatusResponse
from admin_api.interfaces.daos import DatasetGateway


class HttpIngestionDatasetGateway(DatasetGateway):
    def __init__(self, settings: Settings) -> None:
        self._base = settings.ingestion_api_base_url.rstrip("/")

    def _call(self, method: str, path: str) -> DatasetStatusResponse:
        url = f"{self._base}{path}"
        req = urllib.request.Request(url, method=method, headers={"Content-Type": "application/json"})
        data = b"{}" if method == "POST" else None
        try:
            with urllib.request.urlopen(req, data=data, timeout=20) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            raise DependencyUnavailableError(
                f"Ingestion API error ({exc.code}) for {path}: {detail}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise DependencyUnavailableError(
                f"Ingestion API unreachable at {self._base}: {exc}"
            ) from exc
        return DatasetStatusResponse(**body)

    def get_status(self, dataset_id: str) -> DatasetStatusResponse:
        return self._call("GET", f"/api/v1/ingestion/datasets/{dataset_id}")

    def trigger_download(self, dataset_id: str) -> DatasetStatusResponse:
        return self._call("POST", f"/api/v1/ingestion/datasets/{dataset_id}/acquire")
