"""Membership service: users, memberships, multi-role assignments."""
from __future__ import annotations

import pytest

from org_management_api.common.exceptions import NotFoundError
from org_management_api.dtos.requests import (
    AddMemberRequest,
    CreateOrganizationRequest,
    CreateUserRequest,
)
from org_management_api.services.membership import DefaultMembershipService
from org_management_api.services.organizations import DefaultOrganizationService
from tests.support import (
    FakeMembersDao,
    FakeOrganizationsDao,
    FakeUsersDao,
    Store,
)


def _wire() -> tuple[DefaultMembershipService, DefaultOrganizationService, Store]:
    store = Store()
    orgs_dao = FakeOrganizationsDao(store)
    members = DefaultMembershipService(FakeUsersDao(store), FakeMembersDao(store), orgs_dao)
    orgs = DefaultOrganizationService(orgs_dao)
    return members, orgs, store


def test_add_member_creates_user_and_roles() -> None:
    members, orgs, _ = _wire()
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    user, roles = members.add_member(
        org.org_id, AddMemberRequest(subject="alice", roles=["admin", "viewer"], email="a@x.io"))
    assert user.subject == "alice" and user.email == "a@x.io"
    assert {r.role for r in roles} == {"admin", "viewer"}


def test_add_member_is_idempotent_and_reuses_user() -> None:
    members, orgs, _ = _wire()
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    u1, _ = members.add_member(org.org_id, AddMemberRequest(subject="alice", roles=["admin"]))
    u2, _ = members.add_member(org.org_id, AddMemberRequest(subject="alice", roles=["viewer"]))
    assert u1.user_id == u2.user_id
    listed = members.list_members(org.org_id)
    assert len(listed) == 1
    _, roles = listed[0]
    assert {r.role for r in roles} == {"admin", "viewer"}


def test_member_on_missing_org_raises() -> None:
    members, _, _ = _wire()
    with pytest.raises(NotFoundError):
        members.add_member("nope", AddMemberRequest(subject="alice", roles=["admin"]))


def test_list_orgs_for_user_spans_branches() -> None:
    members, orgs, _ = _wire()
    root = orgs.create(CreateOrganizationRequest(name="Acme"))
    emea = orgs.create(CreateOrganizationRequest(name="EMEA", parent_org_id=root.org_id))
    apac = orgs.create(CreateOrganizationRequest(name="APAC", parent_org_id=root.org_id))
    members.add_member(emea.org_id, AddMemberRequest(subject="bob", roles=["lead"]))
    members.add_member(apac.org_id, AddMemberRequest(subject="bob", roles=["viewer"], inherits_down=False))

    rows = members.list_orgs_for_user("bob")
    by_org = {o.org_id: roles for o, roles in rows}
    assert set(by_org) == {emea.org_id, apac.org_id}
    assert by_org[emea.org_id][0].role == "lead"
    assert by_org[apac.org_id][0].inherits_down is False


def test_create_user_and_missing_user_orgs() -> None:
    members, _, _ = _wire()
    created = members.create_user(CreateUserRequest(subject="carol", display_name="Carol"))
    assert created.subject == "carol" and created.display_name == "Carol"
    with pytest.raises(NotFoundError):
        members.list_orgs_for_user("ghost")
