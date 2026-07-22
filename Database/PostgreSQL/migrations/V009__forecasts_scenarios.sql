-- V009: persisted Predict runs — delivery forecasts + digital-twin scenarios.
-- Owned by the Risk Analytics API (operational state). Each row is one agentic
-- run: its deterministic forecast facts (probabilities, credible interval, slip
-- range, outlook) + drivers/cascades (jsonb) + the grounded LLM narrative and
-- confidence. History is a newest-first list capped at the most recent 100 in the
-- read path — mirrors risk.investigations exactly.

CREATE SCHEMA IF NOT EXISTS risk;

CREATE TABLE IF NOT EXISTS risk.forecasts (
    forecast_id             UUID PRIMARY KEY,
    project_key             TEXT             NOT NULL,
    requested_by            TEXT,
    status                  TEXT             NOT NULL,   -- RUNNING | COMPLETED | FAILED
    on_time_probability     DOUBLE PRECISION,
    probability_low         DOUBLE PRECISION,
    probability_high        DOUBLE PRECISION,
    projected_slip_days_low  INTEGER,
    projected_slip_days_high INTEGER,
    outlook                 TEXT,                         -- on_track | at_risk | off_track
    drivers                 JSONB            NOT NULL DEFAULT '[]'::jsonb,
    bull_case               TEXT,
    bear_case               TEXT,
    would_change_mind       TEXT,
    narrative               TEXT,
    confidence              DOUBLE PRECISION,
    run_id                  TEXT,
    created_at              TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_forecasts_created ON risk.forecasts (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_forecasts_requested_by
    ON risk.forecasts (requested_by, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_forecasts_project ON risk.forecasts (project_key);

CREATE TABLE IF NOT EXISTS risk.scenarios (
    scenario_id                   UUID PRIMARY KEY,
    project_key                   TEXT             NOT NULL,
    requested_by                  TEXT,
    scenario                      TEXT             NOT NULL,
    status                        TEXT             NOT NULL,   -- RUNNING | COMPLETED | FAILED
    base_on_time_probability      DOUBLE PRECISION,
    projected_on_time_probability DOUBLE PRECISION,
    probability_delta             DOUBLE PRECISION,
    base_slip_days                INTEGER,
    projected_slip_days           INTEGER,
    portfolio_risk_delta          DOUBLE PRECISION,
    cascades                      JSONB            NOT NULL DEFAULT '[]'::jsonb,
    narrative                     TEXT,
    confidence                    DOUBLE PRECISION,
    run_id                        TEXT,
    created_at                    TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_scenarios_created ON risk.scenarios (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_scenarios_requested_by
    ON risk.scenarios (requested_by, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_scenarios_project ON risk.scenarios (project_key);
