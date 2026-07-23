"""Organization tree service (materialized-path model).

Owns the invariants of the org tree:
- a root org has ``parent_org_id = None``, ``root_org_id = self``, ``depth = 0``,
  ``level = 1``, ``path = <org_id>``;
- a child derives ``root_org_id`` / ``path`` / ``depth`` / ``level`` from its parent
  (``path = parent.path + '.' + child_id``, ``depth = parent.depth + 1``,
  ``level = parent.level + 1``);
- moving a node reparents it and recomputes path/depth/level/root for the node
  AND every descendant (guarded against cycles).
"""
from __future__ import annotations

from org_management_api.common.exceptions import NotFoundError, ValidationError
from org_management_api.common.utilities import new_id, utc_now
from org_management_api.dtos.common import OrganizationRecord
from org_management_api.dtos.requests import (
    CreateOrganizationRequest,
    MoveOrganizationRequest,
    UpdateOrganizationRequest,
)
from org_management_api.interfaces.daos import OrganizationsDao
from org_management_api.interfaces.services import OrganizationService


class DefaultOrganizationService(OrganizationService):
    def __init__(self, organizations_dao: OrganizationsDao) -> None:
        self._dao = organizations_dao

    def _require(self, org_id: str) -> OrganizationRecord:
        rec = self._dao.get(org_id)
        if rec is None:
            raise NotFoundError(f"organization '{org_id}' not found")
        return rec

    def create(self, request: CreateOrganizationRequest) -> OrganizationRecord:
        org_id = new_id()
        now = utc_now()
        if request.parent_org_id:
            parent = self._require(request.parent_org_id)
            record = OrganizationRecord(
                org_id=org_id,
                parent_org_id=parent.org_id,
                root_org_id=parent.root_org_id,
                path=f"{parent.path}.{org_id}",
                depth=parent.depth + 1,
                level=parent.level + 1,
                name=request.name,
                kind=request.kind,
                status="active",
                created_at=now,
            )
        else:
            # A brand-new root / tenant: it is its own root, path is just itself.
            record = OrganizationRecord(
                org_id=org_id,
                parent_org_id=None,
                root_org_id=org_id,
                path=org_id,
                depth=0,
                level=1,
                name=request.name,
                kind=request.kind,
                status="active",
                created_at=now,
            )
        return self._dao.insert(record)

    def get(self, org_id: str) -> OrganizationRecord:
        return self._require(org_id)

    def children(self, org_id: str) -> list[OrganizationRecord]:
        self._require(org_id)
        return self._dao.children(org_id)

    def subtree(self, org_id: str) -> list[OrganizationRecord]:
        rec = self._require(org_id)
        return self._dao.subtree(rec.path)

    def ancestors(self, org_id: str) -> list[OrganizationRecord]:
        rec = self._require(org_id)
        return self._dao.ancestors(rec.path)

    def update(self, org_id: str, request: UpdateOrganizationRequest) -> OrganizationRecord:
        current = self._require(org_id)
        name = request.name if request.name is not None else current.name
        kind = request.kind if request.kind is not None else current.kind
        updated = self._dao.update(org_id, name, kind)
        if updated is None:  # pragma: no cover - guarded by _require above
            raise NotFoundError(f"organization '{org_id}' not found")
        return updated

    def move(self, org_id: str, request: MoveOrganizationRequest) -> OrganizationRecord:
        node = self._require(org_id)
        new_parent = self._require(request.new_parent_org_id)

        # Cycle guard: a node cannot be moved under itself or one of its descendants.
        if new_parent.org_id == node.org_id or new_parent.path == node.path or \
                new_parent.path.startswith(f"{node.path}."):
            raise ValidationError(
                "cannot move an organization under itself or one of its descendants")

        new_path = f"{new_parent.path}.{node.org_id}"
        depth_delta = (new_parent.depth + 1) - node.depth
        level_delta = (new_parent.level + 1) - node.level
        self._dao.reparent(
            node_id=node.org_id,
            new_parent_id=new_parent.org_id,
            old_path=node.path,
            new_path=new_path,
            new_root_org_id=new_parent.root_org_id,
            depth_delta=depth_delta,
            level_delta=level_delta,
        )
        return self._require(org_id)

    def list_roots(self) -> list[OrganizationRecord]:
        return self._dao.list_roots()

    def list_tenant(self, root_org_id: str) -> list[OrganizationRecord]:
        return self._dao.list_by_root(root_org_id)
