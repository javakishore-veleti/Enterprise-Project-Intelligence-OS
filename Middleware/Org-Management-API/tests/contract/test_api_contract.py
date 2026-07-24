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


def test_children_pagination_and_counts_contract() -> None:
    c = _client()
    root = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    for name in ["Delta", "Alpha", "Charlie"]:
        c.post("/api/v1/orgs", json={"name": name, "parent_org_id": root["org_id"]})

    # Roots list carries child_count without fetching children.
    roots = c.get("/api/v1/orgs").json()["organizations"]
    assert roots[0]["child_count"] == 3
    assert roots[0]["member_count"] == 0

    # First page of children, ordered by name, with paging envelope.
    page = c.get(f"/api/v1/orgs/{root['org_id']}/children?limit=2&offset=0").json()
    assert page["total"] == 3 and page["returned"] == 2
    assert page["limit"] == 2 and page["offset"] == 0
    assert [o["name"] for o in page["organizations"]] == ["Alpha", "Charlie"]

    # Default (no params) still works — first page.
    default = c.get(f"/api/v1/orgs/{root['org_id']}/children").json()
    assert len(default["organizations"]) == 3


def test_children_filter_and_sort_contract() -> None:
    c = _client()
    root = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    for name in ["Platform", "Payments", "Marketing"]:
        c.post("/api/v1/orgs", json={"name": name, "parent_org_id": root["org_id"]})

    # `q` filters the direct children; `total` reflects the filtered count.
    filtered = c.get(f"/api/v1/orgs/{root['org_id']}/children?q=p").json()
    assert filtered["total"] == 2
    assert [o["name"] for o in filtered["organizations"]] == ["Payments", "Platform"]

    # Paging over a filtered set.
    page = c.get(f"/api/v1/orgs/{root['org_id']}/children?q=p&limit=1&offset=1").json()
    assert page["total"] == 2 and [o["name"] for o in page["organizations"]] == ["Platform"]

    # `sort=child_count` is accepted (whitelist); an unknown value is rejected.
    ok = c.get(f"/api/v1/orgs/{root['org_id']}/children?sort=child_count")
    assert ok.status_code == 200
    bad = c.get(f"/api/v1/orgs/{root['org_id']}/children?sort=drop_table")
    assert bad.status_code == 422


def test_roles_endpoint_contract() -> None:
    c = _client()
    org = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    c.post(f"/api/v1/orgs/{org['org_id']}/members",
           json={"subject": "alice", "roles": ["admin", "manager"], "inherits_down": True})
    c.post(f"/api/v1/orgs/{org['org_id']}/members",
           json={"subject": "bob", "roles": ["admin", "viewer"], "inherits_down": True})

    allr = c.get("/api/v1/roles").json()
    assert allr["roles"] == ["admin", "manager", "viewer"] and allr["total"] == 3

    man = c.get("/api/v1/roles?q=man").json()
    assert man["roles"] == ["manager"] and man["total"] == 1

    capped = c.get("/api/v1/roles?q=a&limit=1").json()
    assert len(capped["roles"]) == 1 and capped["total"] == 2


def test_org_search_contract() -> None:
    c = _client()
    acme = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    c.post("/api/v1/orgs", json={"name": "Acme Sales", "parent_org_id": acme["org_id"]})
    globex = c.post("/api/v1/orgs", json={"name": "Globex"}).json()
    c.post("/api/v1/orgs", json={"name": "Acme Corp", "parent_org_id": globex["org_id"]})

    allm = c.get("/api/v1/orgs/search?q=acme").json()
    assert allm["total"] == 3
    assert {o["name"] for o in allm["organizations"]} == {"Acme", "Acme Sales", "Acme Corp"}
    # Each item carries path + level + child_count for the "where it sits" UI.
    top = next(o for o in allm["organizations"] if o["name"] == "Acme")
    assert top["level"] == 1 and top["child_count"] == 1 and "path" in top

    scoped = c.get(f"/api/v1/orgs/search?q=acme&root={acme['org_id']}").json()
    assert {o["name"] for o in scoped["organizations"]} == {"Acme", "Acme Sales"}


def test_members_paging_filter_and_inherited_roles_contract() -> None:
    c = _client()
    root = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    emea = c.post("/api/v1/orgs", json={"name": "EMEA", "parent_org_id": root["org_id"]}).json()

    c.post(f"/api/v1/orgs/{root['org_id']}/members",
           json={"subject": "alice", "roles": ["admin"], "inherits_down": True})
    c.post(f"/api/v1/orgs/{emea['org_id']}/members",
           json={"subject": "alice", "roles": ["lead"]})
    c.post(f"/api/v1/orgs/{emea['org_id']}/members",
           json={"subject": "bob", "roles": ["viewer"]})

    # Paged list with envelope + member_count on the org.
    page = c.get(f"/api/v1/orgs/{emea['org_id']}/members?limit=1&offset=0").json()
    assert page["total"] == 2 and page["returned"] == 1 and page["limit"] == 1

    # role filter
    leads = c.get(f"/api/v1/orgs/{emea['org_id']}/members?role=lead").json()["members"]
    assert [m["subject"] for m in leads] == ["alice"]

    # q filter
    found = c.get(f"/api/v1/orgs/{emea['org_id']}/members?q=ali").json()["members"]
    assert [m["subject"] for m in found] == ["alice"]

    # inherited-role resolution for alice (admin inherited from Acme root).
    alice = next(m for m in c.get(f"/api/v1/orgs/{emea['org_id']}/members").json()["members"]
                 if m["subject"] == "alice")
    assert {r["role"] for r in alice["direct_roles"]} == {"lead"}
    assert [r["role"] for r in alice["inherited_roles"]] == ["admin"]
    assert alice["inherited_roles"][0]["source_org_name"] == "Acme"

    # member_count surfaces on the org record.
    assert c.get(f"/api/v1/orgs/{emea['org_id']}").json()["member_count"] == 2


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


def test_org_stats_contract() -> None:
    c = _client()
    acme = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    emea = c.post("/api/v1/orgs", json={"name": "EMEA", "parent_org_id": acme["org_id"]}).json()
    c.post("/api/v1/orgs", json={"name": "Sales", "parent_org_id": emea["org_id"]})
    globex = c.post("/api/v1/orgs", json={"name": "Globex"}).json()
    # A member + a repo so members/repos counts are exercised.
    c.post(f"/api/v1/orgs/{emea['org_id']}/members", json={"subject": "alice", "roles": ["viewer"]})
    c.post(f"/api/v1/orgs/{acme['org_id']}/repositories",
           json={"provider": "jira", "visibility_scope": "org"})

    # Whole platform: 4 orgs across 2 roots — computed WITHOUT any subtree fetch.
    stats = c.get("/api/v1/orgs/stats").json()
    assert stats == {
        "total_orgs": 4, "root_count": 2, "total_members": 1, "total_repositories": 1,
    }

    # Scoped to the Acme tenant only (Globex excluded).
    scoped = c.get(f"/api/v1/orgs/stats?root={acme['org_id']}").json()
    assert scoped["total_orgs"] == 3 and scoped["root_count"] == 1
    assert scoped["total_members"] == 1 and scoped["total_repositories"] == 1
    # Globex tenant: just itself, no members/repos.
    other = c.get(f"/api/v1/orgs/stats?root={globex['org_id']}").json()
    assert other == {
        "total_orgs": 1, "root_count": 1, "total_members": 0, "total_repositories": 0,
    }


def test_repositories_paging_and_search_contract() -> None:
    c = _client()
    org = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    for prov, acct in [("jira", "acme-jira"), ("github", "acme-gh"), ("jira", "team-jira")]:
        c.post(f"/api/v1/orgs/{org['org_id']}/repositories",
               json={"provider": prov, "external_account": acct, "visibility_scope": "org"})

    # Default list carries the paging envelope + all 3 repos.
    listed = c.get(f"/api/v1/orgs/{org['org_id']}/repositories").json()
    assert listed["total"] == 3 and listed["returned"] == 3 and listed["offset"] == 0

    # Page size 2.
    page = c.get(f"/api/v1/orgs/{org['org_id']}/repositories?limit=2&offset=0").json()
    assert page["total"] == 3 and len(page["repositories"]) == 2 and page["limit"] == 2

    # `q` filters on provider / external_account.
    ghs = c.get(f"/api/v1/orgs/{org['org_id']}/repositories?q=github").json()
    assert ghs["total"] == 1 and ghs["repositories"][0]["provider"] == "github"
    jiras = c.get(f"/api/v1/orgs/{org['org_id']}/repositories?q=jira").json()
    assert jiras["total"] == 2


def test_repository_projects_and_grants_list_paging_contract() -> None:
    c = _client()
    org = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    other = c.post("/api/v1/orgs", json={"name": "Globex"}).json()
    third = c.post("/api/v1/orgs", json={"name": "Initech"}).json()
    repo = c.post(f"/api/v1/orgs/{org['org_id']}/repositories",
                  json={"provider": "jira", "visibility_scope": "shared"}).json()
    repo_id = repo["repo_id"]
    c.post(f"/api/v1/repositories/{repo_id}/projects",
           json={"projects": [{"external_key": "SAKAI", "name": "Sakai"},
                              {"external_key": "SPR", "name": "Spring"},
                              {"external_key": "MVN", "name": "Maven"}]})

    # Paged tracker-projects list (new GET endpoint).
    proj = c.get(f"/api/v1/repositories/{repo_id}/projects?limit=2&offset=0").json()
    assert proj["repo_id"] == repo_id and proj["total"] == 3 and len(proj["projects"]) == 2

    # `q` on external_key / name.
    spr = c.get(f"/api/v1/repositories/{repo_id}/projects?q=spr").json()
    assert spr["total"] == 1 and spr["projects"][0]["external_key"] == "SPR"

    # Paged grants list (new GET endpoint).
    c.post(f"/api/v1/repositories/{repo_id}/grants",
           json={"grantee_org_id": other["org_id"], "direction": "org"})
    c.post(f"/api/v1/repositories/{repo_id}/grants",
           json={"grantee_org_id": third["org_id"], "direction": "subtree"})
    grants = c.get(f"/api/v1/repositories/{repo_id}/grants?limit=1&offset=0").json()
    assert grants["repo_id"] == repo_id and grants["total"] == 2 and len(grants["grants"]) == 1


def test_effective_access_paging_and_search_contract() -> None:
    c = _client()
    org = c.post("/api/v1/orgs", json={"name": "Acme"}).json()
    repo = c.post(f"/api/v1/orgs/{org['org_id']}/repositories",
                  json={"provider": "jira", "visibility_scope": "org"}).json()
    c.post(f"/api/v1/repositories/{repo['repo_id']}/projects",
           json={"projects": [{"external_key": "SAKAI", "name": "Sakai"},
                              {"external_key": "SPR", "name": "Spring"}]})
    c.post(f"/api/v1/orgs/{org['org_id']}/members", json={"subject": "alice", "roles": ["viewer"]})

    # visible-projects: paged envelope + `q`.
    vis = c.get("/api/v1/users/alice/visible-projects?limit=1&offset=0").json()
    assert vis["subject"] == "alice" and vis["total"] == 2 and len(vis["projects"]) == 1
    filtered = c.get("/api/v1/users/alice/visible-projects?q=sak").json()
    assert filtered["total"] == 1 and filtered["projects"][0]["external_key"] == "SAKAI"

    # effective-projects: same envelope.
    eff = c.get(f"/api/v1/orgs/{org['org_id']}/effective-projects?limit=1").json()
    assert eff["org_id"] == org["org_id"] and eff["total"] == 2 and len(eff["projects"]) == 1

    # No-param call still returns the full (unpaged-feel) list under the cap.
    plain = c.get("/api/v1/users/alice/visible-projects").json()
    assert {p["external_key"] for p in plain["projects"]} == {"SAKAI", "SPR"}


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
