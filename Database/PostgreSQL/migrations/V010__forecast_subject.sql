-- V010: forecast subject scoping — a forecast can target a whole project
-- (default) or a sub-project subject: a release, component, or tag. Owned by the
-- Risk Analytics API. Defaults keep every pre-existing row reading as a
-- whole-project forecast. Idempotent (IF NOT EXISTS), auto-applied by
-- apply_migrations.py.

ALTER TABLE risk.forecasts
    ADD COLUMN IF NOT EXISTS subject_type  TEXT NOT NULL DEFAULT 'project',  -- project | release | component | tag
    ADD COLUMN IF NOT EXISTS subject_value TEXT;

CREATE INDEX IF NOT EXISTS ix_forecasts_subject
    ON risk.forecasts (project_key, subject_type, subject_value);
