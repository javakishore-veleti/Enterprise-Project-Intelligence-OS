-- V008: persisted Investigation Agent runs (operational state).
-- Owned by the Risk Analytics API. Each row is one autonomous investigation:
-- its conclusion (root cause + causal chain), the reasoning trace + evidence
-- citations (jsonb), the template used, and who requested it. History is a
-- newest-first list capped at the most recent 100 in the read path.

CREATE SCHEMA IF NOT EXISTS risk;

CREATE TABLE IF NOT EXISTS risk.investigations (
    investigation_id   UUID PRIMARY KEY,
    project_key        TEXT        NOT NULL,
    requested_by       TEXT,
    question           TEXT,
    template_key       TEXT,
    status             TEXT        NOT NULL,   -- RUNNING | COMPLETED | FAILED
    root_cause         TEXT,
    confidence         DOUBLE PRECISION,
    recommended_action TEXT,
    hypotheses         JSONB       NOT NULL DEFAULT '[]'::jsonb,
    causal_chain       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    steps              JSONB       NOT NULL DEFAULT '[]'::jsonb,
    evidence           JSONB       NOT NULL DEFAULT '[]'::jsonb,
    run_id             TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_investigations_created ON risk.investigations (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_investigations_requested_by
    ON risk.investigations (requested_by, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_investigations_project ON risk.investigations (project_key);
