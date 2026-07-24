"""Unit tests for the Phase-2 org-scope seam (ported from Projects-API): the HTTP
org-access gateway (parsing + graceful degradation), the ``narrow_with_org_scope``
composition, and the ``provide_org_scope`` header dependency. All hermetic —
``urlopen`` is monkeypatched, no network.
"""
from __future__ import annotations

import io
import json
import urllib.error

from risk_analytics_api.api.dependencies import provide_org_scope
from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.utilities import narrow_with_org_scope
from risk_analytics_api.daos.org_gateway import HttpOrgAccessGateway
from risk_analytics_api.dtos.common import OrgScope
from risk_analytics_api.interfaces.daos import OrgAccessGateway


class FakeOrgGateway(OrgAccessGateway):
    """In-memory org-access gateway (no network). ``down`` simulates the org API
    being unreachable -> both resolvers return None."""

    def __init__(self, visible=None, effective=None, down=False) -> None:
        self._visible = visible or {}
        self._effective = effective or {}
        self._down = down

    def visible_project_keys(self, subject: str):
        return None if self._down else list(self._visible.get(subject, []))

    def effective_project_keys(self, org_id: str):
        return None if self._down else list(self._effective.get(org_id, []))


# --- narrow_with_org_scope composition ------------------------------------- #
def test_narrow_no_org_scope_is_passthrough() -> None:
    assert narrow_with_org_scope(None, None) is None
    assert narrow_with_org_scope(["A", "B"], None) == ["A", "B"]


def test_narrow_org_scope_only_becomes_the_filter() -> None:
    scope = OrgScope(project_keys=("A", "B"))
    assert narrow_with_org_scope(None, scope) == ["A", "B"]


def test_narrow_ands_org_scope_with_projects_filter() -> None:
    # intersection, preserving the existing filter order (deterministic)
    scope = OrgScope(project_keys=("B", "C", "Z"))
    assert narrow_with_org_scope(["A", "B", "C"], scope) == ["B", "C"]


def test_narrow_empty_org_scope_yields_empty_not_all() -> None:
    assert narrow_with_org_scope(None, OrgScope(project_keys=())) == []
    assert narrow_with_org_scope(["A", "B"], OrgScope(project_keys=())) == []


# --- provide_org_scope header resolution ----------------------------------- #
def test_provide_org_scope_no_headers_is_none() -> None:
    gw = FakeOrgGateway(visible={"bob": ["CALM"]})
    assert provide_org_scope(x_org_subject=None, x_org_key=None, gateway=gw) is None


def test_provide_org_scope_subject_uses_visible_projects() -> None:
    gw = FakeOrgGateway(visible={"bob": ["CALM", "SPARK"]})
    scope = provide_org_scope(x_org_subject="bob", x_org_key=None, gateway=gw)
    assert isinstance(scope, OrgScope)
    assert set(scope.project_keys) == {"CALM", "SPARK"}


def test_provide_org_scope_org_key_wins_and_uses_effective_projects() -> None:
    gw = FakeOrgGateway(
        visible={"bob": ["CALM"]}, effective={"org-1": ["RISKY", "CALM"]}
    )
    # X-Org-Key present -> effective_projects for the org, ignoring subject.
    scope = provide_org_scope(x_org_subject="bob", x_org_key="org-1", gateway=gw)
    assert set(scope.project_keys) == {"RISKY", "CALM"}


def test_provide_org_scope_empty_visible_is_present_but_empty() -> None:
    gw = FakeOrgGateway(visible={"bob": []})
    scope = provide_org_scope(x_org_subject="bob", x_org_key=None, gateway=gw)
    assert isinstance(scope, OrgScope) and scope.project_keys == ()


def test_provide_org_scope_gateway_down_degrades_to_none() -> None:
    # org API unreachable -> resolver returns None -> no org scope (graceful).
    gw = FakeOrgGateway(down=True)
    assert provide_org_scope(x_org_subject="bob", x_org_key=None, gateway=gw) is None
    assert provide_org_scope(x_org_subject=None, x_org_key="org-1", gateway=gw) is None


# --- HttpOrgAccessGateway parsing + graceful degradation ------------------- #
def _resp(payload: dict):
    class _Ctx:
        def __enter__(self_inner):
            return io.BytesIO(json.dumps(payload).encode())

        def __exit__(self_inner, *a):
            return False

    return _Ctx()


def _gateway() -> HttpOrgAccessGateway:
    return HttpOrgAccessGateway(Settings())


def test_http_gateway_extracts_external_keys(monkeypatch) -> None:
    payload = {
        "subject": "bob",
        "projects": [
            {"external_key": "CALM", "name": "Calm", "repo_id": "r1",
             "org_id": "o1", "provider": "jira"},
            {"external_key": "SPARK", "name": "Spark", "repo_id": "r1",
             "org_id": "o1", "provider": "jira"},
            {"external_key": "CALM", "name": "dup", "repo_id": "r2",
             "org_id": "o2", "provider": "jira"},  # de-duplicated
        ],
    }
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=10: _resp(payload)
    )
    assert _gateway().visible_project_keys("bob") == ["CALM", "SPARK"]


def test_http_gateway_effective_projects(monkeypatch) -> None:
    payload = {"org_id": "org-1", "projects": [
        {"external_key": "RISKY", "repo_id": "r", "org_id": "o", "provider": "jira"}]}
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=10: _resp(payload)
    )
    assert _gateway().effective_project_keys("org-1") == ["RISKY"]


def test_http_gateway_unreachable_returns_none(monkeypatch) -> None:
    def _boom(req, timeout=10):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert _gateway().visible_project_keys("bob") is None
    assert _gateway().effective_project_keys("org-1") is None


def test_http_gateway_http_error_returns_none(monkeypatch) -> None:
    def _boom(req, timeout=10):
        raise urllib.error.HTTPError("url", 500, "err", {}, io.BytesIO(b"boom"))

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert _gateway().visible_project_keys("bob") is None
