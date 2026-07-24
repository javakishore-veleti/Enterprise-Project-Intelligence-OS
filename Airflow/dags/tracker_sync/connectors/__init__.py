"""Tracker connectors + a provider -> connector factory.

``build_connector(provider, staging_db)`` selects the connector implementation
from the repository's ``provider`` (``org.repositories.provider``). Today only
``fake`` is wired (replays the ``jira_repos`` staging DB); ``jira`` / ``azure_devops``
are ABC-conformant stubs proving the seam.
"""
from __future__ import annotations

from typing import Any

from tracker_sync.connectors.base import TrackerConnector
from tracker_sync.connectors.fake_connector import FakeConnector
from tracker_sync.connectors.live_stubs import AdoConnector, JiraConnector

__all__ = [
    "TrackerConnector",
    "FakeConnector",
    "JiraConnector",
    "AdoConnector",
    "build_connector",
]


def build_connector(provider: str, staging_db: Any = None) -> TrackerConnector:
    """Return a connector for ``provider``.

    ``staging_db`` is the ``jira_repos`` Mongo handle the FakeConnector replays;
    the live connectors ignore it (they read a remote REST API from config).
    """
    key = (provider or "").lower()
    if key == "fake":
        return FakeConnector(staging_db)
    if key == "jira":
        return JiraConnector()
    if key in ("azure_devops", "ado"):
        return AdoConnector()
    raise ValueError(f"unknown tracker provider '{provider}' (known: fake, jira, azure_devops)")
