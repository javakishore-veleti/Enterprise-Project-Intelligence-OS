"""Repository service: create, tracker projects, visibility, grants."""
from __future__ import annotations

import pytest

from org_management_api.common.exceptions import NotFoundError
from org_management_api.dtos.common import Provider, VisibilityScope
from org_management_api.dtos.requests import (
    AddGrantRequest,
    AddTrackerProjectsRequest,
    CreateOrganizationRequest,
    CreateRepositoryRequest,
    TrackerProjectInput,
    UpdateVisibilityRequest,
)
from org_management_api.services.organizations import DefaultOrganizationService
from org_management_api.services.repositories import DefaultRepositoryService
from tests.support import FakeOrganizationsDao, FakeRepositoriesDao, Store


def _wire() -> tuple[DefaultRepositoryService, DefaultOrganizationService, Store]:
    store = Store()
    orgs_dao = FakeOrganizationsDao(store)
    repos = DefaultRepositoryService(FakeRepositoriesDao(store), orgs_dao)
    orgs = DefaultOrganizationService(orgs_dao)
    return repos, orgs, store


def test_create_repository_inherits_root_org() -> None:
    repos, orgs, _ = _wire()
    root = orgs.create(CreateOrganizationRequest(name="Acme"))
    emea = orgs.create(CreateOrganizationRequest(name="EMEA", parent_org_id=root.org_id))
    repo = repos.create_repository(
        emea.org_id,
        CreateRepositoryRequest(provider=Provider.JIRA, external_account="acme-jira",
                                visibility_scope=VisibilityScope.SUBTREE))
    assert repo.org_id == emea.org_id
    assert repo.root_org_id == root.org_id   # tenant boundary carried onto the repo
    assert repo.provider == "jira" and repo.visibility_scope == "subtree"


def test_add_tracker_projects_bulk_and_idempotent() -> None:
    repos, orgs, _ = _wire()
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    repo = repos.create_repository(org.org_id, CreateRepositoryRequest(provider=Provider.JIRA))
    created = repos.add_tracker_projects(repo.repo_id, AddTrackerProjectsRequest(projects=[
        TrackerProjectInput(external_key="SAKAI", name="Sakai"),
        TrackerProjectInput(external_key="SPR", name="Spring"),
    ]))
    assert {p.external_key for p in created} == {"SAKAI", "SPR"}
    # re-adding SAKAI with a new name upserts (no duplicate id/row)
    again = repos.add_tracker_projects(repo.repo_id, AddTrackerProjectsRequest(projects=[
        TrackerProjectInput(external_key="SAKAI", name="Sakai CLE"),
    ]))
    assert again[0].tracker_project_id == created[0].tracker_project_id


def test_set_visibility_and_missing_repo() -> None:
    repos, orgs, _ = _wire()
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    repo = repos.create_repository(org.org_id, CreateRepositoryRequest(provider=Provider.GITHUB))
    updated = repos.set_visibility(
        repo.repo_id, UpdateVisibilityRequest(visibility_scope=VisibilityScope.TENANT))
    assert updated.visibility_scope == "tenant"
    with pytest.raises(NotFoundError):
        repos.set_visibility("nope", UpdateVisibilityRequest(visibility_scope=VisibilityScope.ORG))


def test_add_grant_requires_existing_grantee() -> None:
    repos, orgs, _ = _wire()
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    other = orgs.create(CreateOrganizationRequest(name="Globex"))
    repo = repos.create_repository(
        org.org_id,
        CreateRepositoryRequest(provider=Provider.JIRA, visibility_scope=VisibilityScope.SHARED))
    grant = repos.add_grant(repo.repo_id, AddGrantRequest(grantee_org_id=other.org_id))
    assert grant.grantee_org_id == other.org_id and grant.direction == "org"
    with pytest.raises(NotFoundError):
        repos.add_grant(repo.repo_id, AddGrantRequest(grantee_org_id="ghost"))
