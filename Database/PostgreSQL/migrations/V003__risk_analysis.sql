-- V003: risk-analysis run + findings persistence (operational state).
-- Owned by the Risk Analytics API.

CREATE SCHEMA IF NOT EXISTS risk;

CREATE TABLE IF NOT EXISTS risk.graph_runs (
    run_id      TEXT PRIMARY KEY,
    project_key TEXT        NOT NULL,
    status      TEXT        NOT NULL,
    agent_keys  JSONB       NOT NULL DEFAULT '[]'::jsonb,
    started_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_graph_runs_project ON risk.graph_runs (project_key);

CREATE TABLE IF NOT EXISTS risk.risk_findings (
    finding_id          TEXT PRIMARY KEY,
    run_id              TEXT        NOT NULL REFERENCES risk.graph_runs (run_id),
    project_key         TEXT        NOT NULL,
    agent_key           TEXT        NOT NULL,
    risk_category       TEXT        NOT NULL,
    probability         DOUBLE PRECISION NOT NULL,
    impact              DOUBLE PRECISION NOT NULL,
    severity            TEXT        NOT NULL,
    score               DOUBLE PRECISION NOT NULL,
    confidence          DOUBLE PRECISION NOT NULL,
    explanation         TEXT        NOT NULL,
    assumptions         JSONB       NOT NULL DEFAULT '[]'::jsonb,
    recommended_actions JSONB       NOT NULL DEFAULT '[]'::jsonb,
    affected            JSONB       NOT NULL DEFAULT '[]'::jsonb,
    analysis_timestamp  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_risk_findings_run ON risk.risk_findings (run_id);
CREATE INDEX IF NOT EXISTS ix_risk_findings_project ON risk.risk_findings (project_key);
