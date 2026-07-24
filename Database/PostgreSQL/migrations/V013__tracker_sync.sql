-- V013: tracker-repository sync tracking log (two-level: run + project, plus
-- per-batch checkpoints for resumable, concurrency-safe, non-monolithic sync).
--
-- The Airflow `tracker_repository_sync` DAG replays an org's tracker repository
-- (Jira / ADO / a FakeConnector over the jira_repos staging DB) into the Mongo
-- evidence store in bounded, idempotent batches. Progress is governed here via
-- the Ingestion-API (never written by the DAG directly). Mirrors V007's
-- ingestion_batches/ingestion_log machinery, one level deeper (per project).
--
-- Correlation invariant: `sync_run_id` == the Airflow dag_run_id of the run.
-- The Ingestion-API generates it, passes it as BOTH the dag_run_id and a conf
-- key when triggering the DAG, and every row below keys off it. So the Airflow
-- UI run name, the "Sync now" response, and these tracking rows share one id.

-- Sync-run level: one row per sync run.
CREATE TABLE IF NOT EXISTS ingestion.sync_runs (
    sync_run_id         TEXT PRIMARY KEY,          -- == Airflow dag_run_id
    repo_id             TEXT        NOT NULL,
    org_id              TEXT        NOT NULL,
    root_org_id         TEXT        NOT NULL,
    provider            TEXT        NOT NULL,       -- fake | jira | azure_devops
    since               TIMESTAMPTZ NULL,           -- delta watermark for this run (NULL = full sync)
    status              TEXT        NOT NULL DEFAULT 'RUNNING',  -- RUNNING|COMPLETED|FAILED
    projects_intended   JSONB       NOT NULL DEFAULT '[]'::jsonb, -- project keys the run planned to import
    projects_considered INTEGER     NOT NULL DEFAULT 0,           -- projects the connector actually listed
    projects_total      INTEGER     NOT NULL DEFAULT 0,           -- projects that reached COMPLETED
    issues_total        BIGINT      NOT NULL DEFAULT 0,           -- issues imported across all projects
    requested_by        TEXT        NOT NULL DEFAULT 'system',
    message             TEXT        NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_sync_runs_repo ON ingestion.sync_runs (repo_id, started_at DESC);

-- Project level: one row per (sync_run, project). The per-project completion
-- tracker. Counters (issues_imported / batches_done) are updated with atomic SQL
-- increments so concurrent batch completions never lose an update.
CREATE TABLE IF NOT EXISTS ingestion.sync_run_projects (
    sync_run_id     TEXT        NOT NULL REFERENCES ingestion.sync_runs (sync_run_id),
    project_key     TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'PENDING',  -- PENDING|IN_PROGRESS|COMPLETED|FAILED
    issues_intended INTEGER     NOT NULL DEFAULT 0,          -- issues the plan counted
    issues_imported BIGINT      NOT NULL DEFAULT 0,          -- issues committed so far (atomic +=)
    batches_total   INTEGER     NOT NULL DEFAULT 0,          -- batch windows the plan produced
    batches_done    INTEGER     NOT NULL DEFAULT 0,          -- batches committed so far (atomic +=)
    started_at      TIMESTAMPTZ NULL,
    completed_at    TIMESTAMPTZ NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (sync_run_id, project_key)
);

CREATE INDEX IF NOT EXISTS ix_sync_run_projects_run ON ingestion.sync_run_projects (sync_run_id);

-- Batch level: one row per committed batch window. UNIQUE (run, project, batch)
-- makes commits idempotent and drives the resume-skip (the DAG asks which batch
-- numbers are already committed and skips them on re-run).
CREATE TABLE IF NOT EXISTS ingestion.sync_batches (
    batch_id      TEXT PRIMARY KEY,
    sync_run_id   TEXT        NOT NULL,
    project_key   TEXT        NOT NULL,
    batch_no      INTEGER     NOT NULL,
    source_offset BIGINT      NOT NULL DEFAULT 0,
    record_count  INTEGER     NOT NULL DEFAULT 0,
    status        TEXT        NOT NULL DEFAULT 'COMMITTED',
    attempts      INTEGER     NOT NULL DEFAULT 1,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (sync_run_id, project_key, batch_no)   -- idempotent + resume-safe
);

CREATE INDEX IF NOT EXISTS ix_sync_batches_run ON ingestion.sync_batches (sync_run_id, project_key);
