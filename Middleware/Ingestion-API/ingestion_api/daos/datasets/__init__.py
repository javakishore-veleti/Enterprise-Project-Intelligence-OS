"""PostgreSQL-backed persistence of dataset-acquisition status."""
from __future__ import annotations

from ingestion_api.daos.connection import Database
from ingestion_api.dtos.responses import DatasetStatusResponse
from ingestion_api.interfaces.daos import DatasetsDao

_COLUMNS = (
    "dataset_id, title, state, file_name, source_url, expected_md5, size_bytes, "
    "downloaded_bytes, message, zenodo_record, downloaded_at, updated_at"
)


def _row(r: tuple) -> DatasetStatusResponse:
    return DatasetStatusResponse(
        dataset_id=r[0], title=r[1], state=r[2], file_name=r[3], source_url=r[4],
        expected_md5=r[5], size_bytes=r[6], downloaded_bytes=r[7], message=r[8],
        zenodo_record=r[9], downloaded_at=r[10], updated_at=r[11],
    )


class PostgresDatasetsDao(DatasetsDao):
    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, dataset_id: str) -> DatasetStatusResponse | None:
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {_COLUMNS} FROM ingestion.datasets WHERE dataset_id = %s", (dataset_id,)
            )
            row = cur.fetchone()
            return _row(row) if row else None

    def update_status(self, dataset_id, state, *, downloaded_bytes=None, downloaded_path=None,
                      message=None, set_downloaded_at=False):
        sets = ["state = %s", "updated_at = now()"]
        params: list = [state]
        if downloaded_bytes is not None:
            sets.append("downloaded_bytes = %s"); params.append(downloaded_bytes)
        if downloaded_path is not None:
            sets.append("downloaded_path = %s"); params.append(downloaded_path)
        if message is not None:
            sets.append("message = %s"); params.append(message)
        if set_downloaded_at:
            sets.append("downloaded_at = now()")
        params.append(dataset_id)
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE ingestion.datasets SET {', '.join(sets)} "
                f"WHERE dataset_id = %s RETURNING {_COLUMNS}",
                tuple(params),
            )
            row = cur.fetchone()
            return _row(row) if row else None
