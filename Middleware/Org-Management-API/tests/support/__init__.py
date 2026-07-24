"""In-memory fakes implementing the DAO ports (no Postgres).

These back the hermetic unit + contract tests. Each fake stores typed records
in dicts and faithfully mirrors the semantics of the production SQL — in
particular ``FakeOrganizationsDao.reparent`` reproduces the materialized-path
prefix rewrite, and ``FakeAccessDao`` reproduces the visibility-scope predicate
(org/subtree/ancestors/tenant/shared) exactly as the SQL does. So the tests
exercise the intended tenancy algebra without real infra.
"""
from __future__ import annotations

from datetime import datetime, timezone

from org_management_api.common.utilities import new_id
from org_management_api.dtos.common import (
    InheritedRoleRecord,
    MemberPage,
    MemberRecord,
    OrganizationPage,
    OrganizationRecord,
    RepositoryGrantRecord,
    RepositoryRecord,
    RoleAssignmentRecord,
    TrackerProjectRecord,
    UserRecord,
    VisibleProjectRecord,
)
from org_management_api.interfaces.daos import (
    AccessDao,
    MembersDao,
    OrganizationsDao,
    RepositoriesDao,
    UsersDao,
)


def _now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


class Store:
    """Shared in-memory backing state for the fake DAOs."""

    def __init__(self) -> None:
        self.orgs: dict[str, OrganizationRecord] = {}
        self.users: dict[str, UserRecord] = {}                 # subject -> user
        self.memberships: set[tuple[str, str]] = set()          # (user_id, org_id)
        self.roles: dict[tuple[str, str, str], bool] = {}       # (user_id, org_id, role) -> inherits
        self.repos: dict[str, RepositoryRecord] = {}
        self.tracker: dict[str, dict[str, TrackerProjectRecord]] = {}  # repo_id -> key -> tp
        self.grants: dict[tuple[str, str], str] = {}            # (repo_id, grantee_org_id) -> direction


def _under(descendant_path: str, ancestor_path: str) -> bool:
    """True iff `descendant_path` is strictly below `ancestor_path`."""
    return descendant_path.startswith(f"{ancestor_path}.")


class FakeOrganizationsDao(OrganizationsDao):
    def __init__(self, store: Store) -> None:
        self._s = store

    def _decorate(self, rec: OrganizationRecord) -> OrganizationRecord:
        """Attach child_count + member_count, mirroring the production DAO."""
        child_count = sum(1 for o in self._s.orgs.values() if o.parent_org_id == rec.org_id)
        member_count = sum(1 for (_uid, oid) in self._s.memberships if oid == rec.org_id)
        return rec.model_copy(update={"child_count": child_count, "member_count": member_count})

    def insert(self, record: OrganizationRecord) -> OrganizationRecord:
        self._s.orgs[record.org_id] = record
        return record

    def get(self, org_id: str) -> OrganizationRecord | None:
        rec = self._s.orgs.get(org_id)
        return self._decorate(rec) if rec else None

    def children(self, org_id: str, limit: int = 50, offset: int = 0) -> OrganizationPage:
        rows = sorted(
            (o for o in self._s.orgs.values() if o.parent_org_id == org_id),
            key=lambda o: (o.name, o.org_id))
        page = [self._decorate(o) for o in rows[offset:offset + limit]]
        return OrganizationPage(organizations=page, total=len(rows), offset=offset, limit=limit)

    def search(self, q: str, root: str | None, limit: int, offset: int) -> OrganizationPage:
        needle = q.lower()
        rows = [
            o for o in self._s.orgs.values()
            if needle in o.name.lower() and (root is None or o.root_org_id == root)
        ]
        rows.sort(key=lambda o: (o.name, o.org_id))
        page = [self._decorate(o) for o in rows[offset:offset + limit]]
        return OrganizationPage(organizations=page, total=len(rows), offset=offset, limit=limit)

    def subtree(self, path: str) -> list[OrganizationRecord]:
        rows = [o for o in self._s.orgs.values() if o.path == path or _under(o.path, path)]
        return sorted(rows, key=lambda o: o.path)

    def ancestors(self, path: str) -> list[OrganizationRecord]:
        rows = [o for o in self._s.orgs.values() if _under(path, o.path)]
        return sorted(rows, key=lambda o: o.level)

    def update(self, org_id: str, name: str, kind: str | None) -> OrganizationRecord | None:
        rec = self._s.orgs.get(org_id)
        if rec is None:
            return None
        rec = rec.model_copy(update={"name": name, "kind": kind})
        self._s.orgs[org_id] = rec
        return rec

    def list_roots(self) -> list[OrganizationRecord]:
        rows = sorted(
            (o for o in self._s.orgs.values() if o.parent_org_id is None),
            key=lambda o: (o.name, o.org_id))
        return [self._decorate(o) for o in rows]

    def list_by_root(self, root_org_id: str) -> list[OrganizationRecord]:
        rows = [o for o in self._s.orgs.values() if o.root_org_id == root_org_id]
        return sorted(rows, key=lambda o: o.path)

    def reparent(self, node_id, new_parent_id, old_path, new_path,
                 new_root_org_id, depth_delta, level_delta) -> None:
        # Mirror the SQL: rewrite path prefix for the node + all descendants.
        for oid, o in list(self._s.orgs.items()):
            if o.path == old_path or _under(o.path, old_path):
                suffix = o.path[len(old_path):]
                self._s.orgs[oid] = o.model_copy(update={
                    "path": new_path + suffix,
                    "depth": o.depth + depth_delta,
                    "level": o.level + level_delta,
                    "root_org_id": new_root_org_id,
                })
        node = self._s.orgs[node_id]
        self._s.orgs[node_id] = node.model_copy(update={"parent_org_id": new_parent_id})


class FakeUsersDao(UsersDao):
    def __init__(self, store: Store) -> None:
        self._s = store

    def get_by_subject(self, subject: str) -> UserRecord | None:
        return self._s.users.get(subject)

    def get_or_create(self, subject, email, display_name) -> UserRecord:
        existing = self._s.users.get(subject)
        if existing is not None:
            return existing
        user = UserRecord(
            user_id=new_id(), subject=subject, email=email,
            display_name=display_name, created_at=_now())
        self._s.users[subject] = user
        return user


class FakeMembersDao(MembersDao):
    def __init__(self, store: Store) -> None:
        self._s = store

    def add_membership(self, user_id, org_id) -> None:
        self._s.memberships.add((user_id, org_id))

    def add_role(self, user_id, org_id, role, inherits_down) -> None:
        self._s.roles[(user_id, org_id, role)] = inherits_down

    def _roles_for(self, user_id, org_id) -> list[RoleAssignmentRecord]:
        out = [
            RoleAssignmentRecord(role=role, inherits_down=inh)
            for (uid, oid, role), inh in self._s.roles.items()
            if uid == user_id and oid == org_id
        ]
        return sorted(out, key=lambda r: r.role)

    def _user_by_id(self, user_id) -> UserRecord:
        return next(u for u in self._s.users.values() if u.user_id == user_id)

    def list_members(self, org_id):
        users = sorted(
            (self._user_by_id(uid) for (uid, oid) in self._s.memberships if oid == org_id),
            key=lambda u: u.subject)
        return [(u, self._roles_for(u.user_id, org_id)) for u in users]

    def _inherited_for(self, user_id, ancestor_org_ids) -> list[InheritedRoleRecord]:
        out: list[InheritedRoleRecord] = []
        ancestors = set(ancestor_org_ids)
        for (uid, oid, role), inh in self._s.roles.items():
            if uid != user_id or oid not in ancestors or not inh:
                continue
            src = self._s.orgs.get(oid)
            if src is None:
                continue
            out.append(InheritedRoleRecord(
                role=role, source_org_id=oid,
                source_org_name=src.name, source_org_level=src.level))
        return sorted(out, key=lambda r: (r.source_org_level, r.role))

    def list_members_page(self, org_id, q, role, limit, offset, ancestor_org_ids) -> MemberPage:
        users = [self._user_by_id(uid) for (uid, oid) in self._s.memberships if oid == org_id]
        if q:
            needle = q.lower()
            users = [
                u for u in users
                if needle in (u.subject or "").lower()
                or needle in (u.display_name or "").lower()
                or needle in (u.email or "").lower()
            ]
        if role:
            users = [
                u for u in users
                if any(r.role == role for r in self._roles_for(u.user_id, org_id))
            ]
        users.sort(key=lambda u: (u.subject, u.user_id))
        total = len(users)
        page = users[offset:offset + limit]
        members = [
            MemberRecord(
                user=u,
                direct_roles=self._roles_for(u.user_id, org_id),
                inherited_roles=self._inherited_for(u.user_id, ancestor_org_ids),
            )
            for u in page
        ]
        return MemberPage(members=members, total=total, offset=offset, limit=limit)

    def list_orgs_for_user(self, subject):
        user = self._s.users.get(subject)
        if user is None:
            return []
        orgs = sorted(
            (self._s.orgs[oid] for (uid, oid) in self._s.memberships
             if uid == user.user_id and oid in self._s.orgs),
            key=lambda o: o.path)
        return [(o, self._roles_for(user.user_id, o.org_id)) for o in orgs]


class FakeRepositoriesDao(RepositoriesDao):
    def __init__(self, store: Store) -> None:
        self._s = store

    def insert_repo(self, record: RepositoryRecord) -> RepositoryRecord:
        self._s.repos[record.repo_id] = record
        self._s.tracker.setdefault(record.repo_id, {})
        return record

    def get_repo(self, repo_id) -> RepositoryRecord | None:
        return self._s.repos.get(repo_id)

    def list_by_org(self, org_id) -> list[RepositoryRecord]:
        rows = [r for r in self._s.repos.values() if r.org_id == org_id]
        return sorted(rows, key=lambda r: (r.created_at, r.repo_id))

    def update_visibility(self, repo_id, visibility_scope) -> RepositoryRecord | None:
        rec = self._s.repos.get(repo_id)
        if rec is None:
            return None
        rec = rec.model_copy(update={"visibility_scope": visibility_scope})
        self._s.repos[repo_id] = rec
        return rec

    def insert_tracker_projects(self, repo_id, projects) -> list[TrackerProjectRecord]:
        bucket = self._s.tracker.setdefault(repo_id, {})
        out = []
        for external_key, name in projects:
            existing = bucket.get(external_key)
            tp = TrackerProjectRecord(
                tracker_project_id=existing.tracker_project_id if existing else new_id(),
                repo_id=repo_id, external_key=external_key, name=name)
            bucket[external_key] = tp
            out.append(tp)
        return out

    def list_tracker_projects(self, repo_id) -> list[TrackerProjectRecord]:
        bucket = self._s.tracker.get(repo_id, {})
        return sorted(bucket.values(), key=lambda t: t.external_key)

    def add_grant(self, repo_id, grantee_org_id, direction) -> RepositoryGrantRecord:
        self._s.grants[(repo_id, grantee_org_id)] = direction
        return RepositoryGrantRecord(
            repo_id=repo_id, grantee_org_id=grantee_org_id, direction=direction)


class FakeAccessDao(AccessDao):
    """Mirrors the production visibility predicate in Python."""

    def __init__(self, store: Store) -> None:
        self._s = store

    def _visible(self, a: OrganizationRecord, o: OrganizationRecord, repo: RepositoryRecord) -> bool:
        scope = repo.visibility_scope
        if scope == "org":
            return a.org_id == o.org_id
        if scope == "subtree":
            return a.org_id == o.org_id or _under(a.path, o.path)
        if scope == "ancestors":
            return a.org_id == o.org_id or _under(o.path, a.path)
        if scope == "tenant":
            return a.root_org_id == o.root_org_id
        if scope == "shared":
            for (rid, grantee_org_id), direction in self._s.grants.items():
                if rid != repo.repo_id:
                    continue
                if grantee_org_id == a.org_id:
                    return True
                if direction == "subtree":
                    grantee = self._s.orgs.get(grantee_org_id)
                    if grantee is not None and _under(a.path, grantee.path):
                        return True
            return False
        return False

    def _resolve(self, context_orgs: list[OrganizationRecord]) -> list[VisibleProjectRecord]:
        seen: dict[tuple, VisibleProjectRecord] = {}
        for repo in self._s.repos.values():
            owner = self._s.orgs.get(repo.org_id)
            if owner is None:
                continue
            if not any(self._visible(a, owner, repo) for a in context_orgs):
                continue
            for tp in self._s.tracker.get(repo.repo_id, {}).values():
                key = (tp.external_key, repo.repo_id)
                seen[key] = VisibleProjectRecord(
                    external_key=tp.external_key, name=tp.name, repo_id=repo.repo_id,
                    org_id=repo.org_id, provider=repo.provider)
        return [seen[k] for k in sorted(seen.keys())]

    def visible_projects_for_subject(self, subject) -> list[VisibleProjectRecord]:
        user = self._s.users.get(subject)
        if user is None:
            return []
        context = [
            self._s.orgs[oid] for (uid, oid) in self._s.memberships
            if uid == user.user_id and oid in self._s.orgs
        ]
        return self._resolve(context)

    def effective_projects_for_org(self, org_id) -> list[VisibleProjectRecord]:
        org = self._s.orgs.get(org_id)
        return self._resolve([org] if org else [])
