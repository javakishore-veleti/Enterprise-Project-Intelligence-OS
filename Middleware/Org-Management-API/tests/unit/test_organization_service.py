"""Org tree service: path/depth/level derivation, subtree/ancestors, move."""
from __future__ import annotations

import pytest

from org_management_api.common.exceptions import NotFoundError, ValidationError
from org_management_api.dtos.requests import (
    AddMemberRequest,
    CreateOrganizationRequest,
    MoveOrganizationRequest,
    UpdateOrganizationRequest,
)
from org_management_api.services.membership import DefaultMembershipService
from org_management_api.services.organizations import DefaultOrganizationService
from tests.support import FakeMembersDao, FakeOrganizationsDao, FakeUsersDao, Store


def _service() -> tuple[DefaultOrganizationService, Store]:
    store = Store()
    return DefaultOrganizationService(FakeOrganizationsDao(store)), store


@pytest.fixture
def members_wiring() -> tuple[DefaultMembershipService, DefaultOrganizationService, Store]:
    """A membership service + org service sharing one store (for member_count)."""
    store = Store()
    orgs_dao = FakeOrganizationsDao(store)
    members = DefaultMembershipService(FakeUsersDao(store), FakeMembersDao(store), orgs_dao)
    return members, DefaultOrganizationService(orgs_dao), store


def _create(svc, name, parent=None):
    return svc.create(CreateOrganizationRequest(name=name, parent_org_id=parent))


def test_create_root_is_its_own_tenant() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    assert root.parent_org_id is None
    assert root.root_org_id == root.org_id
    assert root.path == root.org_id
    assert root.depth == 0 and root.level == 1


def test_create_child_derives_path_depth_level() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    branch = _create(svc, "EMEA", parent=root.org_id)
    sub = _create(svc, "Sales", parent=branch.org_id)

    assert branch.root_org_id == root.org_id
    assert branch.path == f"{root.org_id}.{branch.org_id}"
    assert branch.depth == 1 and branch.level == 2

    assert sub.path == f"{root.org_id}.{branch.org_id}.{sub.org_id}"
    assert sub.depth == 2 and sub.level == 3  # 1-indexed level = depth + 1


def test_create_child_of_missing_parent_raises() -> None:
    svc, _ = _service()
    with pytest.raises(NotFoundError):
        _create(svc, "Orphan", parent="does-not-exist")


def test_subtree_and_children_and_ancestors() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    emea = _create(svc, "EMEA", parent=root.org_id)
    apac = _create(svc, "APAC", parent=root.org_id)
    sales = _create(svc, "Sales", parent=emea.org_id)

    subtree_ids = {o.org_id for o in svc.subtree(root.org_id)}
    assert subtree_ids == {root.org_id, emea.org_id, apac.org_id, sales.org_id}

    child_ids = {o.org_id for o in svc.children(root.org_id).organizations}
    assert child_ids == {emea.org_id, apac.org_id}

    ancestors = svc.ancestors(sales.org_id)
    assert [a.org_id for a in ancestors] == [root.org_id, emea.org_id]  # ordered by level


def test_update_renames_without_moving() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    branch = _create(svc, "EMEA", parent=root.org_id)
    updated = svc.update(branch.org_id, UpdateOrganizationRequest(name="Acme EMEA", kind="branch"))
    assert updated.name == "Acme EMEA" and updated.kind == "branch"
    assert updated.path == branch.path and updated.level == branch.level


def test_move_subtree_recomputes_descendants() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    emea = _create(svc, "EMEA", parent=root.org_id)
    sub = _create(svc, "Sales", parent=emea.org_id)
    leaf = _create(svc, "Sales-UK", parent=sub.org_id)
    root2 = _create(svc, "Globex")  # separate tenant

    # levels before: root=1, emea=2, sub=3, leaf=4
    assert (sub.level, leaf.level) == (3, 4)

    # Move `sub` (and its subtree) under root2.
    svc.move(sub.org_id, MoveOrganizationRequest(new_parent_org_id=root2.org_id))

    moved_sub = svc.get(sub.org_id)
    moved_leaf = svc.get(leaf.org_id)

    # Parent + level/depth shift for the moved node...
    assert moved_sub.parent_org_id == root2.org_id
    assert moved_sub.level == 2 and moved_sub.depth == 1
    assert moved_sub.root_org_id == root2.org_id
    assert moved_sub.path == f"{root2.org_id}.{sub.org_id}"

    # ...and the same shift cascades to the descendant.
    assert moved_leaf.level == 3 and moved_leaf.depth == 2
    assert moved_leaf.root_org_id == root2.org_id
    assert moved_leaf.path == f"{root2.org_id}.{sub.org_id}.{leaf.org_id}"

    # The old branch no longer contains the moved subtree.
    emea_subtree = {o.org_id for o in svc.subtree(emea.org_id)}
    assert sub.org_id not in emea_subtree and leaf.org_id not in emea_subtree


def test_move_under_own_descendant_is_rejected() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    emea = _create(svc, "EMEA", parent=root.org_id)
    sub = _create(svc, "Sales", parent=emea.org_id)
    with pytest.raises(ValidationError):
        svc.move(emea.org_id, MoveOrganizationRequest(new_parent_org_id=sub.org_id))
    with pytest.raises(ValidationError):
        svc.move(emea.org_id, MoveOrganizationRequest(new_parent_org_id=emea.org_id))


def test_list_roots_and_tenant() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    _create(svc, "EMEA", parent=root.org_id)
    root2 = _create(svc, "Globex")
    assert {o.org_id for o in svc.list_roots()} == {root.org_id, root2.org_id}
    assert len(svc.list_tenant(root.org_id)) == 2  # root + EMEA


# --- child_count / member_count -------------------------------------------


def test_child_count_is_direct_children_only() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    emea = _create(svc, "EMEA", parent=root.org_id)
    _create(svc, "APAC", parent=root.org_id)
    _create(svc, "Sales", parent=emea.org_id)  # grandchild — NOT counted for root

    roots = {o.org_id: o for o in svc.list_roots()}
    assert roots[root.org_id].child_count == 2  # EMEA + APAC only

    children = {o.org_id: o for o in svc.children(root.org_id).organizations}
    assert children[emea.org_id].child_count == 1   # Sales
    # Single-get also carries the count.
    assert svc.get(emea.org_id).child_count == 1


def test_member_count_counts_memberships(members_wiring) -> None:
    members, orgs, _ = members_wiring
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    members.add_member(org.org_id, AddMemberRequest(subject="alice", roles=["admin"]))
    members.add_member(org.org_id, AddMemberRequest(subject="bob", roles=["viewer"]))
    assert orgs.get(org.org_id).member_count == 2


# --- children pagination ---------------------------------------------------


def test_children_pagination_orders_and_pages() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    for name in ["Delta", "Alpha", "Charlie", "Bravo"]:
        _create(svc, name, parent=root.org_id)

    first = svc.children(root.org_id, limit=2, offset=0)
    assert first.total == 4 and first.limit == 2 and first.offset == 0
    assert [o.name for o in first.organizations] == ["Alpha", "Bravo"]

    second = svc.children(root.org_id, limit=2, offset=2)
    assert [o.name for o in second.organizations] == ["Charlie", "Delta"]
    assert second.total == 4


def test_children_q_filters_by_name_and_total_reflects_filter() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    for name in ["Platform", "Payments", "Marketing", "Sales"]:
        _create(svc, name, parent=root.org_id)

    # Case-insensitive substring on the DIRECT children.
    page = svc.children(root.org_id, limit=25, offset=0, q="p")
    assert page.total == 2  # total reflects the FILTER, not all 4 children
    assert [o.name for o in page.organizations] == ["Payments", "Platform"]

    # No match -> empty page, zero total.
    empty = svc.children(root.org_id, limit=25, offset=0, q="zzz")
    assert empty.total == 0 and empty.organizations == []


def test_children_paging_over_a_filtered_set() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    for name in ["Team A", "Team B", "Team C", "Other"]:
        _create(svc, name, parent=root.org_id)

    first = svc.children(root.org_id, limit=2, offset=0, q="team")
    assert first.total == 3 and [o.name for o in first.organizations] == ["Team A", "Team B"]
    second = svc.children(root.org_id, limit=2, offset=2, q="team")
    assert second.total == 3 and [o.name for o in second.organizations] == ["Team C"]


def test_children_sort_by_child_count_desc_then_created_at() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    big = _create(svc, "Big", parent=root.org_id)
    small = _create(svc, "Small", parent=root.org_id)
    _create(svc, "Empty", parent=root.org_id)
    # Give Big two grandchildren, Small one.
    _create(svc, "b1", parent=big.org_id)
    _create(svc, "b2", parent=big.org_id)
    _create(svc, "s1", parent=small.org_id)

    by_count = svc.children(root.org_id, sort="child_count")
    assert [o.name for o in by_count.organizations] == ["Big", "Small", "Empty"]

    # `created_at` orders newest-first; all three roots' children share a clock in
    # the fake (same _now), so this at least exercises the whitelist path safely.
    by_created = svc.children(root.org_id, sort="created_at")
    assert {o.name for o in by_created.organizations} == {"Big", "Small", "Empty"}


# --- distinct roles (role-picker typeahead) --------------------------------


def test_list_roles_distinct_filtered_and_capped(members_wiring) -> None:
    members, orgs, _ = members_wiring
    org = orgs.create(CreateOrganizationRequest(name="Acme"))
    members.add_member(org.org_id, AddMemberRequest(subject="alice", roles=["admin", "manager"]))
    members.add_member(org.org_id, AddMemberRequest(subject="bob", roles=["admin", "viewer"]))

    # Distinct across assignments (admin appears twice -> once).
    allr = members.list_roles(None, 50)
    assert allr.roles == ["admin", "manager", "viewer"] and allr.total == 3

    # Case-insensitive substring filter.
    man = members.list_roles("MAN", 50)
    assert man.roles == ["manager"] and man.total == 1

    # Cap respected; total still reflects all distinct matches.
    capped = members.list_roles("a", 1)
    assert len(capped.roles) == 1 and capped.total == 2  # admin, manager


# --- search ----------------------------------------------------------------


def test_search_matches_name_case_insensitive_and_scopes_by_root() -> None:
    svc, _ = _service()
    acme = _create(svc, "Acme")
    acme_sales = _create(svc, "Acme Sales", parent=acme.org_id)
    globex = _create(svc, "Globex")
    _create(svc, "Acme Corp", parent=globex.org_id)  # different tenant

    # Unscoped: every "acme" match across tenants.
    unscoped = svc.search("acme", None, limit=25, offset=0)
    assert unscoped.total == 3
    assert {o.name for o in unscoped.organizations} == {"Acme", "Acme Sales", "Acme Corp"}

    # Scoped to the Acme tenant only.
    scoped = svc.search("acme", acme.org_id, limit=25, offset=0)
    assert {o.org_id for o in scoped.organizations} == {acme.org_id, acme_sales.org_id}
    # Items carry the full response fields (path/level/child_count).
    got = {o.org_id: o for o in scoped.organizations}
    assert got[acme.org_id].child_count == 1


def test_search_paginates() -> None:
    svc, _ = _service()
    root = _create(svc, "Acme")
    for i in range(5):
        _create(svc, f"Team {i}", parent=root.org_id)
    page = svc.search("team", None, limit=2, offset=0)
    assert page.total == 5 and len(page.organizations) == 2
