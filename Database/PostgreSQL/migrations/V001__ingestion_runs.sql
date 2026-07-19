-- V001: operational state for dataset ingestion runs.
-- Owned by the Ingestion API. Operational state only (no application/evidence data).

CREATE SCHEMA IF NOT EXISTS ingestion;

CREATE TABLE IF NOT EXISTS ingestion.ingestion_runs (
    run_id       TEXT PRIMARY KEY,
    dataset_id   TEXT        NOT NULL,
    status       TEXT        NOT NULL,
    batch_size   INTEGER     NOT NULL,
    parallelism  INTEGER     NOT NULL,
    requested_by TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ingestion_runs_dataset
    ON ingestion.ingestion_runs (dataset_id);

CREATE INDEX IF NOT EXISTS ix_ingestion_runs_status
    ON ingestion.ingestion_runs (status);
