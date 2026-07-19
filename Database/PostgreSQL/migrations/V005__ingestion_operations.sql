-- V005: ingestion operational sub-operations (acquire/validate/index/reconcile).
-- One table backs all four operation types; the type-specific result is stored
-- in the `result` JSONB column. Owned by the Ingestion API.

CREATE TABLE IF NOT EXISTS ingestion.operations (
    operation_id TEXT PRIMARY KEY,
    op_type      TEXT        NOT NULL,   -- acquisition | validation | index | reconciliation
    dataset_id   TEXT        NOT NULL,
    status       TEXT        NOT NULL,
    params       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    result       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_operations_type ON ingestion.operations (op_type);
CREATE INDEX IF NOT EXISTS ix_operations_dataset ON ingestion.operations (dataset_id);
