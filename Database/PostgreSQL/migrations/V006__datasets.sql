-- V006: dataset acquisition status (Initial Dataset download tracking).
-- Seeds the public Jira dataset (Zenodo record 15719919). Owned by the
-- Ingestion API; the Airflow acquire DAG updates state as it downloads.

CREATE TABLE IF NOT EXISTS ingestion.datasets (
    dataset_id       TEXT PRIMARY KEY,
    title            TEXT        NOT NULL,
    zenodo_record    TEXT,
    file_name        TEXT        NOT NULL,
    source_url       TEXT        NOT NULL,
    expected_md5     TEXT        NOT NULL,
    size_bytes       BIGINT      NOT NULL DEFAULT 0,
    state            TEXT        NOT NULL DEFAULT 'NOT_DOWNLOADED',  -- NOT_DOWNLOADED|DOWNLOADING|DOWNLOADED|FAILED
    downloaded_path  TEXT,
    downloaded_bytes BIGINT      NOT NULL DEFAULT 0,
    message          TEXT        NOT NULL DEFAULT '',
    downloaded_at    TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO ingestion.datasets
    (dataset_id, title, zenodo_record, file_name, source_url, expected_md5, size_bytes, state, updated_at)
VALUES (
    'public-jira',
    'The Public Jira Dataset',
    '15719919',
    '2025-06-23 ThePublicJiraDataset.zip',
    'https://zenodo.org/api/records/15719919/files/2025-06-23%20ThePublicJiraDataset.zip/content',
    '02f85309d966092ea130ca0797aea795',
    5813135238,
    'NOT_DOWNLOADED',
    now()
)
ON CONFLICT (dataset_id) DO NOTHING;
