-- V004: risk-review pipeline persistence.
-- Adds processor annotations to findings and a table for generated reports.

ALTER TABLE risk.risk_findings
    ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS risk.reports (
    report_id    TEXT PRIMARY KEY,
    run_id       TEXT        NOT NULL REFERENCES risk.graph_runs (run_id),
    project_key  TEXT        NOT NULL,
    kind         TEXT        NOT NULL,          -- mitigation | project | executive
    title        TEXT        NOT NULL,
    summary      TEXT        NOT NULL,
    sections     JSONB       NOT NULL DEFAULT '[]'::jsonb,
    source_agent TEXT        NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_reports_run ON risk.reports (run_id);
CREATE INDEX IF NOT EXISTS ix_reports_project ON risk.reports (project_key);
