-- V012: organization + multi-tenancy foundation (Phase 1 of ORG-TENANCY.md).
-- Isolation model: shared schema + row scoping. Every operational/evidence row
-- ultimately carries `root_org_id` (tenant boundary); this migration owns the
-- tenancy schema itself. Org tree uses a PORTABLE materialized path (dotted
-- ancestor uuids ending in self) -- no ltree extension required. Owned by the
-- Org-Management-API.

CREATE SCHEMA IF NOT EXISTS org;

-- Organizations: arbitrary-depth tree. A distinct `root_org_id` = a separate
-- tenant/tree. `path` = dotted ancestor uuids ending in self ("<root>.<...>.<self>").
-- `depth` is 0-indexed (root = 0); `level` is 1-indexed (root = 1, level = depth + 1).
CREATE TABLE IF NOT EXISTS org.organizations (
    org_id        UUID        PRIMARY KEY,
    parent_org_id UUID        NULL REFERENCES org.organizations (org_id),
    root_org_id   UUID        NOT NULL,
    path          TEXT        NOT NULL,
    depth         INTEGER     NOT NULL,
    level         INTEGER     NOT NULL,   -- 1-indexed (root = 1 = depth + 1)
    name          TEXT        NOT NULL,
    kind          TEXT        NULL,
    status        TEXT        NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_org_root       ON org.organizations (root_org_id);
CREATE INDEX IF NOT EXISTS ix_org_parent     ON org.organizations (parent_org_id);
CREATE INDEX IF NOT EXISTS ix_org_root_level ON org.organizations (root_org_id, level);
-- text-pattern index so `path LIKE '<prefix>.%'` (subtree/ancestor prefix scans) is cheap.
CREATE INDEX IF NOT EXISTS ix_org_path_pattern
    ON org.organizations (path text_pattern_ops);

-- Global user identity (SSO subject). A user may belong to many orgs/branches.
CREATE TABLE IF NOT EXISTS org.users (
    user_id      UUID        PRIMARY KEY,
    subject      TEXT        NOT NULL UNIQUE,   -- SSO subject / global identity
    email        TEXT        NULL,
    display_name TEXT        NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS org.memberships (
    user_id    UUID        NOT NULL REFERENCES org.users (user_id),
    org_id     UUID        NOT NULL REFERENCES org.organizations (org_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, org_id)
);

CREATE INDEX IF NOT EXISTS ix_memberships_org ON org.memberships (org_id);

-- Many roles per user per org; a role may inherit down the subtree or be branch-scoped.
CREATE TABLE IF NOT EXISTS org.role_assignments (
    user_id       UUID    NOT NULL REFERENCES org.users (user_id),
    org_id        UUID    NOT NULL REFERENCES org.organizations (org_id),
    role          TEXT    NOT NULL,
    inherits_down BOOLEAN NOT NULL DEFAULT true,
    PRIMARY KEY (user_id, org_id, role)
);

-- A connected tracker account (provider-agnostic). `visibility_scope` drives
-- cross-org/tenant visibility of its tracker_projects.
CREATE TABLE IF NOT EXISTS org.repositories (
    repo_id           UUID        PRIMARY KEY,
    org_id            UUID        NOT NULL REFERENCES org.organizations (org_id),
    root_org_id       UUID        NOT NULL,
    provider          TEXT        NOT NULL,   -- jira | github | azure_devops
    external_account  TEXT        NULL,
    connection_config JSONB       NOT NULL DEFAULT '{}'::jsonb,
    visibility_scope  TEXT        NOT NULL DEFAULT 'org',  -- org|subtree|ancestors|tenant|shared
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_repositories_org  ON org.repositories (org_id);
CREATE INDEX IF NOT EXISTS ix_repositories_root ON org.repositories (root_org_id);

-- Tracker projects (Jira projects / GitHub repos / ADO projects) under a repo.
CREATE TABLE IF NOT EXISTS org.tracker_projects (
    tracker_project_id UUID PRIMARY KEY,
    repo_id            UUID NOT NULL REFERENCES org.repositories (repo_id),
    external_key       TEXT NOT NULL,
    name               TEXT NULL
);

CREATE INDEX IF NOT EXISTS ix_tracker_projects_repo ON org.tracker_projects (repo_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_tracker_projects_repo_key
    ON org.tracker_projects (repo_id, external_key);

-- Explicit cross-tree / cross-tenant sharing of a repository to another org.
CREATE TABLE IF NOT EXISTS org.repository_grants (
    repo_id        UUID NOT NULL REFERENCES org.repositories (repo_id),
    grantee_org_id UUID NOT NULL REFERENCES org.organizations (org_id),
    direction      TEXT NOT NULL DEFAULT 'org',  -- org | subtree (grant to grantee's descendants too)
    PRIMARY KEY (repo_id, grantee_org_id)
);

CREATE INDEX IF NOT EXISTS ix_repository_grants_grantee
    ON org.repository_grants (grantee_org_id);
