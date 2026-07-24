"""Live-tracker connector stubs (Jira / Azure DevOps).

These prove the ABC seam is provider-agnostic without pulling in a live tracker
yet. Each is a drop-in ``TrackerConnector``; implementing the four methods against
a real REST API (using ``connection_config`` url/token) is the ONLY work needed to
go live — the sync engine, normalization, stamping, batching, tracking and
tracker-project registration downstream stay exactly as they are.

Deliberately NOT implemented here (next step, once a live instance exists):
building the real REST clients + auth. Left as clearly-marked TODO seams.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from tracker_sync.connectors.base import TrackerConnector


class JiraConnector(TrackerConnector):
    """Jira REST v2/v3 connector (TODO — not yet implemented).

    ``connection_config`` shape (planned)::

        {"base_url": "https://acme.atlassian.net", "email": "...",
         "api_token": "<secret, never committed>", "jql": "<optional filter>"}
    """

    provider = "jira"

    def test_connection(self, config: Dict[str, Any]) -> bool:
        # TODO: GET {base_url}/rest/api/2/myself with basic auth (email:api_token).
        raise NotImplementedError("JiraConnector.test_connection — implement against Jira REST")

    def list_projects(self, config: Dict[str, Any]) -> List[Dict[str, str]]:
        # TODO: GET {base_url}/rest/api/2/project -> [{"external_key": p["key"], "name": p["name"]}]
        raise NotImplementedError("JiraConnector.list_projects — implement against Jira REST")

    def count_issues(
        self, config: Dict[str, Any], project_key: str, since: Optional[datetime] = None
    ) -> int:
        # TODO: POST {base_url}/rest/api/2/search JQL `project = {key} [AND updated >= since]`
        #       maxResults=0 -> read the `total` field.
        raise NotImplementedError("JiraConnector.count_issues — implement against Jira REST")

    def fetch_issues(
        self, config: Dict[str, Any], project_key: str, since: Optional[datetime] = None,
        offset: Optional[int] = None, limit: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        # TODO: POST .../search JQL `project = {key} [AND updated >= since]` ORDER BY key,
        #       startAt=offset, maxResults=limit, expand=changelog,
        #       fields=... -> yield each raw issue dict (already the shape transform_issue reads).
        raise NotImplementedError("JiraConnector.fetch_issues — implement against Jira REST")


class AdoConnector(TrackerConnector):
    """Azure DevOps Work Items connector (TODO — not yet implemented).

    ``connection_config`` shape (planned)::

        {"organization": "acme", "project": "...", "pat": "<secret>"}

    The ADO client must map Work Items into the raw Jira-REST shape
    ``transform_issue`` expects (key, fields.status.name, changelog.histories,
    fields.issuelinks, ...) so normalization stays connector-independent.
    """

    provider = "azure_devops"

    def test_connection(self, config: Dict[str, Any]) -> bool:
        raise NotImplementedError("AdoConnector.test_connection — implement against ADO REST")

    def list_projects(self, config: Dict[str, Any]) -> List[Dict[str, str]]:
        raise NotImplementedError("AdoConnector.list_projects — implement against ADO REST")

    def count_issues(
        self, config: Dict[str, Any], project_key: str, since: Optional[datetime] = None
    ) -> int:
        raise NotImplementedError("AdoConnector.count_issues — implement against ADO REST")

    def fetch_issues(
        self, config: Dict[str, Any], project_key: str, since: Optional[datetime] = None,
        offset: Optional[int] = None, limit: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError("AdoConnector.fetch_issues — implement against ADO REST")
