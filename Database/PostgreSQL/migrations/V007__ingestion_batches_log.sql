-- V007: batch checkpoints + ingestion log for resumable, non-monolithic
-- record ingestion. The Airflow project_dataset_ingest DAG streams records in
-- batches, committing a checkpoint per batch (resume) and appending progress to
-- the log (the Admin UI polls this). Run-level status stays in ingestion_runs.

CREATE TABLE IF NOT EXISTS ingestion.ingestion_batches (
    batch_id      TEXT PRIMARY KEY,
    run_id        TEXT        NOT NULL,
    entity        TEXT        NOT NULL,
    batch_no      INTEGER     NOT NULL,
    source_offset BIGINT      NOT NULL DEFAULT 0,
    record_count  INTEGER     NOT NULL DEFAULT 0,
    status        TEXT        NOT NULL DEFAULT 'COMMITTED',
    attempts      INTEGER     NOT NULL DEFAULT 1,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, entity, batch_no)   -- idempotent per (run, entity, batch): resume-safe
);

CREATE INDEX IF NOT EXISTS ix_batches_run ON ingestion.ingestion_batches (run_id);

CREATE TABLE IF NOT EXISTS ingestion.ingestion_log (
    log_id        TEXT PRIMARY KEY,
    run_id        TEXT        NOT NULL,
    level         TEXT        NOT NULL DEFAULT 'INFO',
    entity        TEXT,
    message       TEXT        NOT NULL,
    records_done  BIGINT      NOT NULL DEFAULT 0,
    records_total BIGINT      NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ingestion_log_run ON ingestion.ingestion_log (run_id, created_at);
