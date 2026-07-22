-- V011: persisted Decide runs — Options-first prescriptive decision support.
-- Owned by the Risk Analytics API (operational state). Each row is one decision:
-- an agentic run that produced 2-3 decision options (jsonb), the grounded LLM
-- narrative + confidence, the option the user selected, and the approval record.
-- Statuses: DRAFTED (options generated) -> SELECTED (an option chosen) ->
-- APPROVED (approved as a preview/dry-run — NO external tickets created); FAILED
-- if the options agent errored. History is a newest-first list capped at the most
-- recent 100 in the read path — mirrors risk.forecasts / risk.investigations.

CREATE SCHEMA IF NOT EXISTS risk;

CREATE TABLE IF NOT EXISTS risk.decisions (
    decision_id         UUID PRIMARY KEY,
    project_key         TEXT             NOT NULL,
    requested_by        TEXT,
    status              TEXT             NOT NULL,   -- DRAFTED | SELECTED | APPROVED | FAILED
    options             JSONB            NOT NULL DEFAULT '[]'::jsonb,
    selected_option_id  TEXT,
    narrative           TEXT,
    confidence          DOUBLE PRECISION,
    run_id              TEXT,
    created_at          TIMESTAMPTZ      NOT NULL DEFAULT now(),
    approved_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_decisions_created ON risk.decisions (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_decisions_requested_by
    ON risk.decisions (requested_by, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_decisions_project ON risk.decisions (project_key);
