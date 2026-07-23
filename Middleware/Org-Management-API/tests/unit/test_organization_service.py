"""Org tree service: path/depth/level derivation, subtree/ancestors, move."""
from __future__ import annotations

import pytest

from org_management_api.common.exceptions import NotFoundError, ValidationError
from org_management_api.dtos.requests import (
    CreateOrganizationRequest,
    MoveOrganizationRequest,
    UpdateOrganizationRequest,
)
from org_management_api.services.organizations import DefaultOrganizationService
from tests.support import FakeOrganizationsDao, Store


def _service() -> tuple[DefaultOrganizationService, Store]:
    store = Store()
    return DefaultOrganizationService(FakeOrganizationsDao(store)), store


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

    child_ids = {o.org_id for o in svc.children(root.org_id)}
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
