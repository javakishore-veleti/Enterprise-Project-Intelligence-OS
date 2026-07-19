-- V002: administrative configuration + audit (operational state).
-- Owned by the Admin API. Seeds the 16 specialist agents with platform defaults
-- (LangGraph orchestration, Claude reasoning model), all enabled.

CREATE SCHEMA IF NOT EXISTS admin;

CREATE TABLE IF NOT EXISTS admin.agent_configs (
    agent_key    TEXT PRIMARY KEY,
    display_name TEXT        NOT NULL,
    enabled      BOOLEAN     NOT NULL DEFAULT true,
    model        TEXT        NOT NULL,
    framework    TEXT        NOT NULL,
    prompt_ref   TEXT,
    updated_by   TEXT        NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS admin.audit_events (
    event_id    TEXT PRIMARY KEY,
    entity_type TEXT        NOT NULL,
    entity_key  TEXT        NOT NULL,
    action      TEXT        NOT NULL,
    actor       TEXT        NOT NULL,
    details     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_audit_events_created ON admin.audit_events (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_events_entity ON admin.audit_events (entity_type, entity_key);

-- Seed the 16 specialist agents (idempotent).
INSERT INTO admin.agent_configs (agent_key, display_name, enabled, model, framework, prompt_ref, updated_by, updated_at)
VALUES
    ('project_risk_manager',    'Project Risk Manager',    true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('project_status_tracking', 'Project Status Tracking', true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('schedule_risk',           'Schedule Risk',           true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('quality_risk',            'Quality Risk',            true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('dependency_risk',         'Dependency Risk',         true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('resource_risk',           'Resource Risk',           true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('backlog_health',          'Backlog Health',          true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('delivery_forecasting',    'Delivery Forecasting',    true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('risk_scoring',            'Risk Scoring',            true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('evidence_validation',     'Evidence Validation',     true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('risk_correlation',        'Risk Correlation',        true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('risk_deduplication',      'Risk Deduplication',      true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('mitigation_planning',     'Mitigation Planning',     true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('critic',                  'Critic',                  true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('project_reporting',       'Project Reporting',       true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now()),
    ('executive_reporting',     'Executive Reporting',     true, 'claude-opus-4-8', 'langgraph', NULL, 'system', now())
ON CONFLICT (agent_key) DO NOTHING;
