"""Tracker-agnostic connector contract.

A ``TrackerConnector`` is the seam between "some issue tracker holds an org's
projects and issues" and our evidence store. Every provider — the ``FakeConnector``
(replays the restored ``jira_repos`` staging DB, no live tracker), a real
``JiraConnector`` (Jira REST v2/v3), an ``AdoConnector`` (Azure DevOps Work
Items) — implements THIS interface and nothing else changes downstream: the sync
engine, normalization (``transform_issue``), org-stamping, batching, tracking and
tracker-project registration are all connector-independent.

Contract:
- ``list_projects(config)``   -> the projects the connection exposes.
- ``count_issues(config, project_key, since)`` -> issue count (for batch planning).
- ``fetch_issues(config, project_key, since, offset, limit)`` -> raw provider
  issue dicts, in the *raw Jira-REST shape* ``transform_issue`` consumes. ``since``
  enables delta sync (only issues updated at/after it); ``offset``/``limit`` bound
  a single batch window so batches are independent + parallelizable.
- ``test_connection(config)`` -> cheap liveness probe of the connection.

``config`` is the repository's ``connection_config`` jsonb (provider-specific:
staging repo names for the fake; base_url + auth token for the real ones).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Iterable, Iterator, List, Optional


class TrackerConnector(ABC):
    """Provider-agnostic read interface over an issue tracker."""

    #: Stable provider key (matches ``org.repositories.provider``).
    provider: str = "abstract"

    @abstractmethod
    def test_connection(self, config: Dict[str, Any]) -> bool:
        """Return True if the connection is usable (auth ok / staging present)."""

    @abstractmethod
    def list_projects(self, config: Dict[str, Any]) -> List[Dict[str, str]]:
        """Projects the connection exposes, as ``[{"external_key", "name"}, ...]``."""

    @abstractmethod
    def count_issues(
        self, config: Dict[str, Any], project_key: str, since: Optional[datetime] = None
    ) -> int:
        """Number of issues in a project (respecting ``since``) — used to plan batches."""

    @abstractmethod
    def fetch_issues(
        self,
        config: Dict[str, Any],
        project_key: str,
        since: Optional[datetime] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Yield raw provider issue documents (raw Jira-REST shape).

        ``since`` restricts to issues updated at/after it (delta sync; ``None`` =
        full). ``offset``/``limit`` bound one batch window (``None`` = unbounded).
        The yielded dicts are consumed verbatim by ``transform_issue``.
        """
