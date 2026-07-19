"""Dataset-status DTO (mirrors the Ingestion-API contract)."""
from __future__ import annotations

from datetime import datetime

from admin_api.common.models import TypedModel


class DatasetStatusResponse(TypedModel):
    dataset_id: str
    title: str
    state: str
    file_name: str
    source_url: str
    expected_md5: str
    size_bytes: int
    downloaded_bytes: int
    message: str
    zenodo_record: str | None = None
    downloaded_at: datetime | None = None
    updated_at: datetime
