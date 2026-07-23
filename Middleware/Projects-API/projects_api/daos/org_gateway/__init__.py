"""HTTP gateway to the Org-Management-API effective-access resolver (:8005).

Phase-2 multi-tenancy seam. Read-only: resolves the set of project keys a user
or org context may see, so the evidence read path can scope results to it.

Uses stdlib ``urllib`` (same convention as the Ingestion/Admin gateways — no
extra runtime dependency). The org API being unreachable is handled **gracefully
here**: any transport/HTTP error is logged and surfaced as ``None`` (not an
exception), which the scope dependency treats as *no org scope* — the read path
then behaves exactly as it did before Phase 2 rather than returning a 500.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from projects_api.common.configuration import Settings
from projects_api.common.logging import get_logger
from projects_api.interfaces.daos import OrgAccessGateway

_logger = get_logger(__name__)


def _project_keys(body: dict) -> list[str]:
    """Extract de-duplicated ``external_key`` values (== our ``project_key``)
    from an effective/visible-projects resolver response, preserving order."""
    seen: dict[str, None] = {}
    for proj in body.get("projects", []) or []:
        key = (proj or {}).get("external_key")
        if key:
            seen.setdefault(key, None)
    return list(seen)


class HttpOrgAccessGateway(OrgAccessGateway):
    def __init__(self, settings: Settings) -> None:
        self._base = settings.org_api_base_url.rstrip("/")

    def _get(self, path: str) -> dict | None:
        """GET ``path`` and return the parsed JSON body, or ``None`` if the org
        API is unreachable / errors (logged, never raised)."""
        url = f"{self._base}{path}"
        req = urllib.request.Request(
            url, method="GET", headers={"Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            # URLError also covers HTTPError; ValueError covers bad JSON. Treat
            # all as "org scope unresolvable" -> None (graceful degradation).
            _logger.warning(
                "org-management API unreachable; degrading to no org scope",
                extra={"context": {"base_url": self._base, "path": path, "error": str(exc)}},
            )
            return None

    def visible_project_keys(self, subject: str) -> list[str] | None:
        body = self._get(
            f"/api/v1/users/{urllib.parse.quote(subject, safe='')}/visible-projects"
        )
        return None if body is None else _project_keys(body)

    def effective_project_keys(self, org_id: str) -> list[str] | None:
        body = self._get(
            f"/api/v1/orgs/{urllib.parse.quote(org_id, safe='')}/effective-projects"
        )
        return None if body is None else _project_keys(body)
