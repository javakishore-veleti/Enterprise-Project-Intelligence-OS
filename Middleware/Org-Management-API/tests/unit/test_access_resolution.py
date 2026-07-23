"""Effective-access resolution across all five visibility scopes.

Tenant tree (root=1):
    Acme(root) ─ EMEA ─ Sales
               └ APAC
    Globex(root2) ─ GlobexDiv          (separate tenant)

A repository owned by EMEA carries tracker project SAKAI. For each scope we
assert exactly which org contexts resolve SAKAI as visible.
"""
from __future__ import annotations

from org_management_api.dtos.common import Provider, VisibilityScope
from org_management_api.dtos.requests import (
    AddGrantRequest,
    AddMemberRequest,
    AddTrackerProjectsRequest,
    CreateOrganizationRequest,
    CreateRepositoryRequest,
    TrackerProjectInput,
    UpdateVisibilityRequest,
)
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


class World:
    def __init__(self) -> None:
        store = Store()
        orgs_dao = FakeOrganizationsDao(store)
        self.orgs = DefaultOrganizationService(orgs_dao)
        self.repos = DefaultRepositoryService(FakeRepositoriesDao(store), orgs_dao)
        self.members = DefaultMembershipService(
            FakeUsersDao(store), FakeMembersDao(store), orgs_dao)
        self.access = DefaultAccessService(
            FakeAccessDao(store), FakeUsersDao(store), orgs_dao)

        self.acme = self.orgs.create(CreateOrganizationRequest(name="Acme"))
        self.emea = self._child("EMEA", self.acme)
        self.sales = self._child("Sales", self.emea)
        self.apac = self._child("APAC", self.acme)
        self.globex = self.orgs.create(CreateOrganizationRequest(name="Globex"))
        self.globex_div = self._child("GlobexDiv", self.globex)

        self.repo = self.repos.create_repository(
            self.emea.org_id, CreateRepositoryRequest(provider=Provider.JIRA))
        self.repos.add_tracker_projects(
            self.repo.repo_id,
            AddTrackerProjectsRequest(projects=[TrackerProjectInput(external_key="SAKAI", name="Sakai")]))

    def _child(self, name, parent):
        return self.orgs.create(CreateOrganizationRequest(name=name, parent_org_id=parent.org_id))

    def set_scope(self, scope: VisibilityScope) -> None:
        self.repos.set_visibility(self.repo.repo_id, UpdateVisibilityRequest(visibility_scope=scope))

    def sees(self, org) -> bool:
        keys = {p.external_key for p in self.access.effective_projects_for_org(org.org_id)}
        return "SAKAI" in keys


def test_scope_org_owner_only() -> None:
    w = World()
    w.set_scope(VisibilityScope.ORG)
    assert w.sees(w.emea)
    assert not w.sees(w.sales)   # descendant
    assert not w.sees(w.acme)    # ancestor
    assert not w.sees(w.apac)    # sibling


def test_scope_subtree_cascades_down() -> None:
    w = World()
    w.set_scope(VisibilityScope.SUBTREE)
    assert w.sees(w.emea) and w.sees(w.sales)   # owner + descendant
    assert not w.sees(w.acme)                    # ancestor excluded
    assert not w.sees(w.apac)                    # sibling excluded


def test_scope_ancestors_cascades_up() -> None:
    w = World()
    w.set_scope(VisibilityScope.ANCESTORS)
    assert w.sees(w.emea) and w.sees(w.acme)    # owner + ancestor
    assert not w.sees(w.sales)                   # descendant excluded
    assert not w.sees(w.apac)                    # sibling excluded


def test_scope_tenant_spans_whole_tree() -> None:
    w = World()
    w.set_scope(VisibilityScope.TENANT)
    assert w.sees(w.acme) and w.sees(w.emea) and w.sees(w.sales) and w.sees(w.apac)
    assert not w.sees(w.globex)       # different tenant
    assert not w.sees(w.globex_div)


def test_scope_shared_requires_grant_org_direction() -> None:
    w = World()
    w.set_scope(VisibilityScope.SHARED)
    # No grant yet -> nobody but... nobody (shared ignores tree structure).
    assert not w.sees(w.apac)
    w.repos.add_grant(w.repo.repo_id, AddGrantRequest(grantee_org_id=w.apac.org_id))
    assert w.sees(w.apac)             # explicit grantee
    assert not w.sees(w.emea)         # owner not implicitly visible under 'shared'
    assert not w.sees(w.sales)        # grant is org-direction: no cascade


def test_scope_shared_cross_tenant_and_subtree_direction() -> None:
    w = World()
    w.set_scope(VisibilityScope.SHARED)
    # Grant across tenants to Globex with subtree direction -> Globex + descendants.
    w.repos.add_grant(
        w.repo.repo_id,
        AddGrantRequest(grantee_org_id=w.globex.org_id, direction="subtree"))
    assert w.sees(w.globex)           # cross-tenant grantee
    assert w.sees(w.globex_div)       # descendant of grantee (subtree direction)
    assert not w.sees(w.apac)         # not granted


def test_visible_projects_unions_across_memberships() -> None:
    w = World()
    # Repo1 (EMEA) subtree -> visible to Sales (descendant).
    w.set_scope(VisibilityScope.SUBTREE)
    # Repo2 owned by APAC, org-scope, project SPRING.
    repo2 = w.repos.create_repository(
        w.apac.org_id, CreateRepositoryRequest(provider=Provider.JIRA))
    w.repos.add_tracker_projects(
        repo2.repo_id,
        AddTrackerProjectsRequest(projects=[TrackerProjectInput(external_key="SPRING", name="Spring")]))

    # alice is a member of Sales (sees SAKAI via subtree) AND APAC (sees SPRING via org).
    w.members.add_member(w.sales.org_id, AddMemberRequest(subject="alice", roles=["viewer"]))
    w.members.add_member(w.apac.org_id, AddMemberRequest(subject="alice", roles=["viewer"]))

    keys = {p.external_key for p in w.access.visible_projects_for_subject("alice")}
    assert keys == {"SAKAI", "SPRING"}
