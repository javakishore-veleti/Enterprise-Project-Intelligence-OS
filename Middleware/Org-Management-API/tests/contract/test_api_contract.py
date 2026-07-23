"""Contract tests: drive the HTTP surface end-to-end against in-memory fakes.

Asserts the exact response field names / status codes clients depend on, over
the whole Endpoint -> Facade -> Service -> DAO stack (only the DB is faked).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from org_management_api.api import dependencies as deps
from org_management_api.api.main import create_app
from org_management_api.facades.manage_members import ManageMembersFacade
from org_management_api.facades.manage_organizations import ManageOrganizationsFacade
from org_management_api.facades.manage_repositories import ManageRepositoriesFacade
from org_management_api.facades.resolve_access import ResolveAccessFacade
from org_management_api.services.access import DefaultAccessService
from org_management_api.services.membership import DefaultMembershipService
from org_management_api.services.organizations import DefaultOrganizationService
from org_management_api.services.repositories import DefaultRepositoryService
from tests.support import (
    FakeAccessDao,
    FakeMembersDao,
    FakeOrganizationsDao,
    FakeRepositoriesDao,
    FakeUsersDao,
    Store,
)


def _client() -> TestClient:
    store = Store()
    orgs_dao = FakeOrganizationsDao(store)
    users_dao = FakeUsersDao(store)

    orgs_facade = ManageOrganizationsFacade(DefaultOrganizationService(orgs_dao))
    members_facade = ManageMembersFacade(
        DefaultMembershipService(users_dao, FakeMembersDao(store), orgs_dao))
    repos_facade = ManageRepositoriesFacade(
        DefaultRepositoryService(FakeRepositoriesDao(store), orgs_dao))
    access_facade = ResolveAccessFacade(
        DefaultAccessService(FakeAccessDao(store), users_dao, orgs_dao))

    app = create_app()
    app.dependency_overrides[deps.provide_manage_organizations_facade] = lambda: orgs_facade
    app.dependency_overrides[deps.provide_manage_members_facade] = lambda: members_facade
    app.dependency_overrides[deps.provide_manage_repositories_facade] = lambda: repos_facade
    app.dependency_overrides[deps.provide_resolve_access_facade] = lambda: access_facade
    return TestClient(app)


def test_organization_tree_lifecycle() -> None:
    c = _client()
    root = c.post("/api/v1/orgs", json={"name": "Acme"})
    assert root.status_code == 201
    root_id = root.json()["org_id"]
    assert root.json()["level"] == 1 and root.json()["root_org_id"] == root_id

    emea = c.post("/api/v1/orgs", json={"name": "EMEA", "parent_org_id": root_id}).json()
    sub = c.post("/api/v1/orgs", json={"name": "Sales", "parent_org_id": emea["org_id"]}).json()
    assert emea["level"] == 2 and sub["level"] == 3

    children = c.get(f"/api/v1/orgs/{root_id}/children").json()["organizations"]
    assert [o["name"] for o in children] == ["EMEA"]

    subtree = c.get(f"/api/v1/orgs/{root_id}/subtree").json()["organizations"]
    assert {o["org_id"] for o in subtree} == {root_id, emea["org_id"], sub["org_id"]}

    ancestors = c.get(f"/api/v1/orgs/{sub['org_id']}/ancestors").json()["organizations"]
    assert [o["org_id"] for o in ancestors] == [root_id, emea["org_id"]]

    roots = c.get("/api/v1/orgs").json()["organizations"]
    assert [o["org_id"] for o in roots] == [root_id]

    renamed = c.put(f"/api/v1/orgs/{emea['org_id']}", json={"name": "Acme EMEA"})
    assert renamed.json()["name"] == "Acme EMEA"


def test_move_endpoint_reparents_and_recomputes() -> None:
    c = _client()
    root = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    emea = c.post("/api/v1/orgs", json={"name": "EMEA", "parent_org_id": root["org_id"]}).json()
    sub = c.post("/api/v1/orgs", json={"name": "Sales", "parent_org_id": emea["org_id"]}).json()
    root2 = c.post("/api/v1/orgs", json={"name": "Globex"}).json()

    moved = c.post(f"/api/v1/orgs/{emea['org_id']}/move",
                   json={"new_parent_org_id": root2["org_id"]})
    assert moved.status_code == 200
    assert moved.json()["level"] == 2 and moved.json()["root_org_id"] == root2["org_id"]
    # descendant recomputed
    child = c.get(f"/api/v1/orgs/{sub['org_id']}").json()
    assert child["level"] == 3 and child["root_org_id"] == root2["org_id"]

    # cycle guard -> 422
    bad = c.post(f"/api/v1/orgs/{root2['org_id']}/move",
                 json={"new_parent_org_id": sub["org_id"]})
    assert bad.status_code == 422


def test_missing_org_returns_404() -> None:
    assert _client().get("/api/v1/orgs/does-not-exist").status_code == 404


def test_members_and_user_orgs() -> None:
    c = _client()
    org = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    m = c.post(f"/api/v1/orgs/{org['org_id']}/members",
               json={"subject": "alice", "roles": ["admin", "viewer"], "email": "a@x.io"})
    assert m.status_code == 201
    assert {r["role"] for r in m.json()["roles"]} == {"admin", "viewer"}

    members = c.get(f"/api/v1/orgs/{org['org_id']}/members").json()["members"]
    assert members[0]["subject"] == "alice"

    orgs = c.get("/api/v1/users/alice/orgs").json()
    assert orgs["subject"] == "alice"
    assert orgs["orgs"][0]["org_id"] == org["org_id"]

    created = c.post("/api/v1/users", json={"subject": "bob"})
    assert created.status_code == 201 and created.json()["subject"] == "bob"


def test_repositories_projects_visibility_grants() -> None:
    c = _client()
    org = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    other = c.post("/api/v1/orgs", json={"name": "Globex"}).json()

    repo = c.post(f"/api/v1/orgs/{org['org_id']}/repositories",
                  json={"provider": "jira", "external_account": "acme", "visibility_scope": "org"})
    assert repo.status_code == 201
    repo_id = repo.json()["repo_id"]
    assert repo.json()["root_org_id"] == org["org_id"]

    projects = c.post(f"/api/v1/repositories/{repo_id}/projects",
                      json={"projects": [{"external_key": "SAKAI", "name": "Sakai"},
                                         {"external_key": "SPR", "name": "Spring"}]})
    assert projects.status_code == 201
    assert {p["external_key"] for p in projects.json()["projects"]} == {"SAKAI", "SPR"}

    vis = c.put(f"/api/v1/repositories/{repo_id}/visibility",
                json={"visibility_scope": "shared"})
    assert vis.json()["visibility_scope"] == "shared"

    grant = c.post(f"/api/v1/repositories/{repo_id}/grants",
                   json={"grantee_org_id": other["org_id"], "direction": "org"})
    assert grant.status_code == 201 and grant.json()["grantee_org_id"] == other["org_id"]

    listed = c.get(f"/api/v1/orgs/{org['org_id']}/repositories").json()
    assert listed["repositories"][0]["repo_id"] == repo_id


def test_effective_and_visible_projects_endpoints() -> None:
    c = _client()
    org = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    repo = c.post(f"/api/v1/orgs/{org['org_id']}/repositories",
                  json={"provider": "jira", "visibility_scope": "org"}).json()
    c.post(f"/api/v1/repositories/{repo['repo_id']}/projects",
           json={"projects": [{"external_key": "SAKAI", "name": "Sakai"}]})
    c.post(f"/api/v1/orgs/{org['org_id']}/members",
           json={"subject": "alice", "roles": ["viewer"]})

    eff = c.get(f"/api/v1/orgs/{org['org_id']}/effective-projects").json()
    assert eff["org_id"] == org["org_id"]
    assert {p["external_key"] for p in eff["projects"]} == {"SAKAI"}

    vis = c.get("/api/v1/users/alice/visible-projects").json()
    assert vis["subject"] == "alice"
    assert vis["projects"][0]["external_key"] == "SAKAI"
    assert vis["projects"][0]["provider"] == "jira"
