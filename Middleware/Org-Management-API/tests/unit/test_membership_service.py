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


# --- paged / filtered members ---------------------------------------------


def test_list_members_page_paginates_and_orders() -> None:
    members, orgs, _ = _wire()
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    for subj in ["dave", "alice", "carol", "bob"]:
        members.add_member(org.org_id, AddMemberRequest(subject=subj, roles=["viewer"]))

    first = members.list_members_page(org.org_id, None, None, limit=2, offset=0)
    assert first.total == 4 and first.limit == 2 and first.offset == 0
    assert [m.user.subject for m in first.members] == ["alice", "bob"]  # ordered by subject

    second = members.list_members_page(org.org_id, None, None, limit=2, offset=2)
    assert [m.user.subject for m in second.members] == ["carol", "dave"]


def test_list_members_page_q_and_role_filters() -> None:
    members, orgs, _ = _wire()
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    members.add_member(org.org_id, AddMemberRequest(
        subject="alice", roles=["admin"], display_name="Alice Ng", email="alice@x.io"))
    members.add_member(org.org_id, AddMemberRequest(subject="bob", roles=["viewer"]))

    # q matches display_name substring, case-insensitive.
    by_q = members.list_members_page(org.org_id, "ng", None, limit=25, offset=0)
    assert [m.user.subject for m in by_q.members] == ["alice"]

    # role filter keeps only members holding that direct role.
    by_role = members.list_members_page(org.org_id, None, "viewer", limit=25, offset=0)
    assert [m.user.subject for m in by_role.members] == ["bob"]


def test_list_members_page_resolves_inherited_roles_from_ancestors() -> None:
    members, orgs, _ = _wire()
    root = orgs.create(CreateOrganizationRequest(name="Acme"))
    emea = orgs.create(CreateOrganizationRequest(name="EMEA", parent_org_id=root.org_id))

    # alice is an admin at the ROOT with inherits_down=true, and a member of EMEA.
    members.add_member(root.org_id, AddMemberRequest(subject="alice", roles=["admin"], inherits_down=True))
    members.add_member(emea.org_id, AddMemberRequest(subject="alice", roles=["lead"]))
    # bob holds a NON-inheriting role at root; it must NOT surface in EMEA.
    members.add_member(root.org_id, AddMemberRequest(subject="bob", roles=["auditor"], inherits_down=False))
    members.add_member(emea.org_id, AddMemberRequest(subject="bob", roles=[]))

    page = members.list_members_page(emea.org_id, None, None, limit=25, offset=0)
    by_subject = {m.user.subject: m for m in page.members}

    alice = by_subject["alice"]
    assert {r.role for r in alice.direct_roles} == {"lead"}
    assert [r.role for r in alice.inherited_roles] == ["admin"]
    assert alice.inherited_roles[0].source_org_id == root.org_id
    assert alice.inherited_roles[0].source_org_name == "Acme"
    assert alice.inherited_roles[0].source_org_level == 1

    bob = by_subject["bob"]
    assert bob.inherited_roles == []  # inherits_down=false is not inherited down


def test_list_members_page_missing_org_raises() -> None:
    members, _, _ = _wire()
    with pytest.raises(NotFoundError):
        members.list_members_page("nope", None, None, limit=25, offset=0)
