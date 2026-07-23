"""Effective-access resolution (the tenancy query surface).

The visibility algebra is one SQL predicate relating a *context* org `a`
(the org from whose vantage point we resolve) to a repository `r`'s *owner*
org `o`, per `r.visibility_scope`:

  - org        : a == o
  - subtree    : a == o OR a is a descendant of o     (a.path under o.path)
  - ancestors  : a == o OR a is an ancestor of o      (o.path under a.path)
  - tenant     : a.root_org_id == o.root_org_id       (same tenant tree)
  - shared     : relies on grants (no base cascade of its own)

Plus, for ANY scope, an explicit repository_grant to `a` (or, direction='subtree',
to an ancestor of a) is ADDITIVE — it makes the repo visible regardless of scope.

`visible_projects_for_subject` runs it for every org the user is a member of;
`effective_projects_for_org` runs it for a single org. Both return the DISTINCT
union of the visible tracker projects. Path-prefix predicates use the
materialized `path` and the text_pattern_ops index.
"""
from __future__ import annotations

from org_management_api.dtos.common import VisibleProjectRecord
from org_management_api.interfaces.daos import AccessDao

# Relates context org `a` to owner org `o` for repository `r`. No bind params:
# every value here is a column reference, so this is safe to embed directly.
# Base scope predicates OR an ADDITIVE grant: an explicit repository_grant makes
# the repo visible to `a` regardless of the base visibility_scope (so a repo can
# be, e.g., 'subtree' to its own branch AND separately granted to a sibling).
# The 'shared' scope simply relies on grants (no base cascade of its own).
_VISIBILITY_PREDICATE = """(
      (r.visibility_scope = 'org'       AND a.org_id = o.org_id)
   OR (r.visibility_scope = 'subtree'   AND (a.org_id = o.org_id OR a.path LIKE o.path || '.%'))
   OR (r.visibility_scope = 'ancestors' AND (a.org_id = o.org_id OR o.path LIKE a.path || '.%'))
   OR (r.visibility_scope = 'tenant'    AND a.root_org_id = o.root_org_id)
   OR EXISTS (
          SELECT 1 FROM org.repository_grants g
          LEFT JOIN org.organizations go ON go.org_id = g.grantee_org_id
          WHERE g.repo_id = r.repo_id
            AND ( g.grantee_org_id = a.org_id
                  OR (g.direction = 'subtree' AND a.path LIKE go.path || '.%') )
       )
)"""

_SELECT = "SELECT DISTINCT tp.external_key, tp.name, r.repo_id, r.org_id, r.provider"
_TRAILER = " ORDER BY tp.external_key, r.repo_id"


def _row(r: tuple) -> VisibleProjectRecord:
    return VisibleProjectRecord(
        external_key=r[0], name=r[1], repo_id=str(r[2]), org_id=str(r[3]), provider=r[4])


class PostgresAccessDao(AccessDao):
    def __init__(self, database) -> None:
        self._db = database

    def visible_projects_for_subject(self, subject: str) -> list[VisibleProjectRecord]:
        sql = (
            f"{_SELECT} "
            "FROM org.users u "
            "JOIN org.memberships m ON m.user_id = u.user_id "
            "JOIN org.organizations a ON a.org_id = m.org_id "
            "JOIN org.repositories r ON TRUE "
            "JOIN org.organizations o ON o.org_id = r.org_id "
            "JOIN org.tracker_projects tp ON tp.repo_id = r.repo_id "
            f"WHERE u.subject = %s AND {_VISIBILITY_PREDICATE}{_TRAILER}"
        )
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (subject,))
            return [_row(r) for r in cur.fetchall()]

    def effective_projects_for_org(self, org_id: str) -> list[VisibleProjectRecord]:
        sql = (
            f"{_SELECT} "
            "FROM org.organizations a "
            "JOIN org.repositories r ON TRUE "
            "JOIN org.organizations o ON o.org_id = r.org_id "
            "JOIN org.tracker_projects tp ON tp.repo_id = r.repo_id "
            f"WHERE a.org_id = %s AND {_VISIBILITY_PREDICATE}{_TRAILER}"
        )
        with self._db.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (org_id,))
            return [_row(r) for r in cur.fetchall()]
