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


class EntityProgress(TypedModel):
    entity: str
    records_done: int
    records_total: int
    status: str


class IngestionLogEntry(TypedModel):
    level: str
    entity: str | None
    message: str
    records_done: int
    records_total: int
    created_at: datetime


class IngestionProgressResponse(TypedModel):
    run_id: str | None
    dataset_id: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_done: int = 0
    records_total: int = 0
    entities: list[EntityProgress] = []
    recent_log: list[IngestionLogEntry] = []
