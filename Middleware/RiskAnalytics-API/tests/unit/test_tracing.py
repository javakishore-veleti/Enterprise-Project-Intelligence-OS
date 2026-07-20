"""Unit tests for the LangSmith tracing bootstrap (no network)."""
from __future__ import annotations

import os

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.tracing import configure_tracing

_LC_VARS = ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT",
            "LANGSMITH_TRACING", "LANGSMITH_PROJECT", "LANGSMITH_API_KEY"]


def _clear(monkeypatch):
    for v in _LC_VARS:
        monkeypatch.delenv(v, raising=False)


def test_disabled_by_default(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-key")
    assert configure_tracing(Settings()) is False  # LANGSMITH_TRACING unset -> off
    assert "LANGCHAIN_TRACING_V2" not in os.environ


def test_enabled_without_key_is_noop(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    assert configure_tracing(Settings()) is False


def test_enabled_with_key_sets_env(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_PROJECT", "epi-os")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-key")

    assert configure_tracing(Settings()) is True
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "epi-os"
    assert os.environ["LANGCHAIN_API_KEY"] == "ls-key"
