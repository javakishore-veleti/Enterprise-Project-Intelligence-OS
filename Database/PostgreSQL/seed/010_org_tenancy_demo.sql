-- Demo org tree for the Org-Management-API (Phase 1 of ORG-TENANCY.md).
-- Idempotent: fixed UUIDs + ON CONFLICT DO NOTHING, so re-running is safe.
-- Not applied automatically; load after migrations for a demonstrable tenant:
--   psql "$PG_URL" -f Database/PostgreSQL/seed/010_org_tenancy_demo.sql
--
-- Tenant "Acme" (root) with two branches (EMEA, APAC) and a sub-branch under
-- EMEA, three users with mixed roles across branches, a Jira repository under
-- EMEA carrying REAL evidence project keys (Sakai, Spring) with subtree
-- visibility, and one `shared` grant of that repo to the sibling branch (APAC).

-- Organizations (materialized path; root level = 1, level = depth + 1) --------
INSERT INTO org.organizations
    (org_id, parent_org_id, root_org_id, path, depth, level, name, kind, status)
VALUES
    ('11111111-1111-1111-1111-111111111111', NULL,
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111', 0, 1, 'Acme', 'company', 'active'),
    ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111.22222222-2222-2222-2222-222222222222',
     1, 2, 'Acme EMEA', 'branch', 'active'),
    ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111.33333333-3333-3333-3333-333333333333',
     1, 2, 'Acme APAC', 'branch', 'active'),
    ('44444444-4444-4444-4444-444444444444', '22222222-2222-2222-2222-222222222222',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111.22222222-2222-2222-2222-222222222222.44444444-4444-4444-4444-444444444444',
     2, 3, 'Acme EMEA Sales', 'team', 'active')
ON CONFLICT (org_id) DO NOTHING;

-- Users -----------------------------------------------------------------------
INSERT INTO org.users (user_id, subject, email, display_name) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', 'alice', 'alice@acme.example', 'Alice Root'),
    ('aaaaaaaa-0000-0000-0000-000000000002', 'bob',   'bob@acme.example',   'Bob EMEA'),
    ('aaaaaaaa-0000-0000-0000-000000000003', 'carol', 'carol@acme.example', 'Carol APAC')
ON CONFLICT (subject) DO NOTHING;

-- Memberships (a user may belong to several orgs/branches) ---------------------
INSERT INTO org.memberships (user_id, org_id) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111'),  -- alice @ Acme root
    ('aaaaaaaa-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222'),  -- bob   @ EMEA
    ('aaaaaaaa-0000-0000-0000-000000000002', '44444444-4444-4444-4444-444444444444'),  -- bob   @ EMEA Sales
    ('aaaaaaaa-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333')   -- carol @ APAC
ON CONFLICT (user_id, org_id) DO NOTHING;

-- Role assignments (many roles per user per org; some inherit down subtree) ----
INSERT INTO org.role_assignments (user_id, org_id, role, inherits_down) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'org_admin',  true),
    ('aaaaaaaa-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222', 'branch_lead', true),
    ('aaaaaaaa-0000-0000-0000-000000000002', '44444444-4444-4444-4444-444444444444', 'viewer',     false),
    ('aaaaaaaa-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333', 'viewer',     true)
ON CONFLICT (user_id, org_id, role) DO NOTHING;

-- Repository (Jira) under EMEA, subtree-visible ------------------------------
INSERT INTO org.repositories
    (repo_id, org_id, root_org_id, provider, external_account, connection_config, visibility_scope)
VALUES
    ('bbbbbbbb-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
     '11111111-1111-1111-1111-111111111111', 'jira', 'acme-emea-jira',
     '{}'::jsonb, 'subtree')
ON CONFLICT (repo_id) DO NOTHING;

-- Tracker projects using REAL evidence project keys ---------------------------
INSERT INTO org.tracker_projects (tracker_project_id, repo_id, external_key, name) VALUES
    ('cccccccc-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001', 'SAKAI',  'Sakai'),
    ('cccccccc-0000-0000-0000-000000000002', 'bbbbbbbb-0000-0000-0000-000000000001', 'SPR',    'Spring Framework')
ON CONFLICT (repo_id, external_key) DO NOTHING;

-- Cross-branch share: grant the EMEA repo to the sibling branch APAC ----------
INSERT INTO org.repository_grants (repo_id, grantee_org_id, direction) VALUES
    ('bbbbbbbb-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333333', 'org')
ON CONFLICT (repo_id, grantee_org_id) DO NOTHING;
