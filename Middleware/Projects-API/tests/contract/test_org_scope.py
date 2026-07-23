"""Contract tests for the Phase-2 org-scope integration over the Projects-API
read path. Real routers/facades/services wired to fake DAOs + a fake org-access
gateway (no Mongo, no network). Exercises:

- ``X-Org-Subject`` / ``X-Org-Key`` narrowing portfolio-summary + search
- empty visible set -> empty results (isolation, not "all")
- no org headers -> behavior 100% unchanged
- org API unreachable -> graceful degradation to no org scope
- org scope AND-composed with the legacy ``X-User-Key`` / ``scope`` seam
- single-project reads 404 when outside the org scope
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from projects_api.api.dependencies import (
    provide_get_project_facade,
    provide_org_gateway,
    provide_portfolio_summary_facade,
    provide_search_projects_scoped_facade,
)
from projects_api.api.main import create_app
from projects_api.common.configuration import Settings
from projects_api.dtos.common import (
    PortfolioAggregate,
    PortfolioScoredRow,
    ProjectSearchScoredRow,
)
from projects_api.dtos.responses import ProjectResponse
from projects_api.facades.get_project import GetProjectFacade
from projects_api.facades.portfolio_summary import PortfolioSummaryFacade
from projects_api.facades.search_projects_scoped import SearchProjectsScopedFacade
from projects_api.interfaces.daos import (
    OrgAccessGateway,
    PortfolioSummaryDao,
    ProjectAssignmentsDao,
)
from projects_api.services.portfolio_summary import DefaultPortfolioSummaryService
from projects_api.services.project_query import DefaultProjectQueryService
from tests.unit.test_org_gateway import FakeOrgGateway
from tests.unit.test_project_query_service import FakeProjectsDao

# --- fixture data ---------------------------------------------------------- #
PORTFOLIO_SCORED = [
    PortfolioScoredRow(project_key="RISKY", name="Risky", category="apache",
                       issue_count=1000, open_issue_count=1000, blocker_count=608,
                       reopen_rate=0.6, issue_aging_days=2067, critical_defect_ratio=0.9),
    PortfolioScoredRow(project_key="CALM", name="Calm", category=None,
                       issue_count=100, open_issue_count=2, blocker_count=0,
                       reopen_rate=0.0, issue_aging_days=5.0, critical_defect_ratio=0.0),
    PortfolioScoredRow(project_key="MID", name="Mid", category=None,
                       issue_count=200, open_issue_count=80, blocker_count=30,
                       reopen_rate=0.4, issue_aging_days=1000, critical_defect_ratio=0.3),
]
AGGREGATE = PortfolioAggregate(
    total_projects=4, total_issues=1300, total_open_issues=1082, scored=PORTFOLIO_SCORED)

SEARCH_ROWS = [
    ProjectSearchScoredRow(project_key="RISKY", name="Risky", open_issue_count=1000,
                           issue_count=1000, has_metrics=True, blocker_count=608,
                           reopen_rate=0.6, issue_aging_days=2067, critical_defect_ratio=0.9),
    ProjectSearchScoredRow(project_key="CALM", name="Calm", open_issue_count=2,
                           issue_count=100, has_metrics=True, blocker_count=0,
                           reopen_rate=0.0, issue_aging_days=5.0, critical_defect_ratio=0.0),
    ProjectSearchScoredRow(project_key="MID", name="Mid", open_issue_count=80,
                           issue_count=200, has_metrics=True, blocker_count=30,
                           reopen_rate=0.4, issue_aging_days=1000, critical_defect_ratio=0.3),
]

# legacy per-user assignment seam
ASSIGNMENTS = {"mgr-rc": ["RISKY", "CALM"]}

# org gateway resolutions (external_key == project_key)
VISIBLE = {"bob": ["CALM"], "carol": ["CALM", "MID"], "empty": []}
EFFECTIVE = {"org-1": ["RISKY", "CALM"]}


class _FakePortfolioDao(PortfolioSummaryDao):
    def portfolio_data(self, project_keys=None, as_of=None):
        scored = list(PORTFOLIO_SCORED)
        totals = (AGGREGATE.total_projects, AGGREGATE.total_issues, AGGREGATE.total_open_issues)
        if project_keys is not None:
            allowed = set(project_keys)
            scored = [r for r in scored if r.project_key in allowed]
            totals = (len(scored), sum(r.issue_count for r in scored),
                      sum(r.open_issue_count for r in scored))
        return PortfolioAggregate(
            total_projects=totals[0], total_issues=totals[1],
            total_open_issues=totals[2], scored=scored)


class _FakeAssignmentsDao(ProjectAssignmentsDao):
    def project_keys_for(self, user_key: str):
        return list(ASSIGNMENTS.get(user_key, []))


def _client(gateway: OrgAccessGateway | None = None) -> TestClient:
    app = create_app()
    gateway = gateway or FakeOrgGateway(visible=VISIBLE, effective=EFFECTIVE)

    portfolio_service = DefaultPortfolioSummaryService(_FakePortfolioDao())
    app.dependency_overrides[provide_portfolio_summary_facade] = (
        lambda: PortfolioSummaryFacade(portfolio_service, _FakeAssignmentsDao()))

    query_service = DefaultProjectQueryService(
        FakeProjectsDao(
            [ProjectResponse(project_key=r.project_key, name=r.name) for r in SEARCH_ROWS],
            SEARCH_ROWS),
        Settings())
    app.dependency_overrides[provide_search_projects_scoped_facade] = (
        lambda: SearchProjectsScopedFacade(query_service, _FakeAssignmentsDao()))
    app.dependency_overrides[provide_get_project_facade] = (
        lambda: GetProjectFacade(query_service))

    app.dependency_overrides[provide_org_gateway] = lambda: gateway
    return TestClient(app)


def _keys(body, field="top_projects"):
    return [p["project_key"] for p in body[field]]


# --- (a) org headers filter results to the gateway's returned keys --------- #
def test_portfolio_summary_scoped_by_org_subject() -> None:
    resp = _client().get("/api/v1/projects/portfolio-summary",
                         headers={"X-Org-Subject": "bob"})  # bob -> [CALM]
    assert resp.status_code == 200
    body = resp.json()
    assert _keys(body) == ["CALM"]
    assert body["scope"]["scoped"] is True
    assert body["totals"]["projects"] == 1


def test_search_scoped_by_org_subject() -> None:
    resp = _client().get("/api/v1/projects/search", headers={"X-Org-Subject": "carol"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(_keys(body, "items")) == {"CALM", "MID"}
    assert body["total"] == 2


def test_portfolio_summary_scoped_by_org_key_uses_effective_projects() -> None:
    resp = _client().get("/api/v1/projects/portfolio-summary",
                         headers={"X-Org-Key": "org-1"})  # -> [RISKY, CALM]
    body = resp.json()
    assert set(_keys(body)) == {"RISKY", "CALM"}
    assert body["totals"]["projects"] == 2


def test_search_scoped_by_org_key() -> None:
    body = _client().get("/api/v1/projects/search",
                         headers={"X-Org-Key": "org-1"}).json()
    assert set(_keys(body, "items")) == {"RISKY", "CALM"}


# --- (b) empty visible set -> empty results (isolation, not "all") --------- #
def test_empty_org_scope_yields_empty_portfolio() -> None:
    body = _client().get("/api/v1/projects/portfolio-summary",
                         headers={"X-Org-Subject": "empty"}).json()
    assert body["top_projects"] == []
    assert body["totals"]["projects"] == 0
    assert body["overall_risk"] == "Low"


def test_empty_org_scope_yields_empty_search() -> None:
    body = _client().get("/api/v1/projects/search",
                         headers={"X-Org-Subject": "empty"}).json()
    assert body["items"] == [] and body["total"] == 0


# --- (c) no org headers -> behavior 100% unchanged ------------------------- #
def test_no_org_headers_portfolio_unchanged() -> None:
    body = _client().get("/api/v1/projects/portfolio-summary").json()
    assert set(_keys(body)) == {"RISKY", "CALM", "MID"}
    assert body["scope"]["scoped"] is False
    assert body["totals"]["projects"] == 4


def test_no_org_headers_search_unchanged() -> None:
    body = _client().get("/api/v1/projects/search").json()
    assert set(_keys(body, "items")) == {"RISKY", "CALM", "MID"}
    assert body["total"] == 3


# --- (d) org API unreachable -> graceful degradation to no org scope ------- #
def test_gateway_down_degrades_to_no_org_scope_portfolio() -> None:
    client = _client(FakeOrgGateway(down=True))
    body = client.get("/api/v1/projects/portfolio-summary",
                      headers={"X-Org-Subject": "bob"}).json()
    # graceful: no 500, and falls back to the full (legacy) view rather than empty
    assert set(_keys(body)) == {"RISKY", "CALM", "MID"}
    assert body["scope"]["scoped"] is False


def test_gateway_down_degrades_to_no_org_scope_search() -> None:
    client = _client(FakeOrgGateway(down=True))
    resp = client.get("/api/v1/projects/search", headers={"X-Org-Key": "org-1"})
    assert resp.status_code == 200
    assert set(_keys(resp.json(), "items")) == {"RISKY", "CALM", "MID"}


# --- org scope AND-composed with the legacy scope seam --------------------- #
def test_org_scope_intersects_with_user_key_assignments() -> None:
    # mgr-rc is assigned [RISKY, CALM]; bob's org scope is [CALM] -> intersection [CALM].
    body = _client().get(
        "/api/v1/projects/portfolio-summary",
        headers={"X-User-Key": "mgr-rc", "X-Org-Subject": "bob"}).json()
    assert _keys(body) == ["CALM"]
    assert "RISKY" not in _keys(body)


def test_org_scope_intersects_with_scope_param_in_search() -> None:
    # scope=mgr-rc -> [RISKY, CALM]; org carol -> [CALM, MID]; intersection -> [CALM].
    body = _client().get(
        "/api/v1/projects/search?scope=mgr-rc", headers={"X-Org-Subject": "carol"}).json()
    assert _keys(body, "items") == ["CALM"]


# --- single-project reads honor the org scope ------------------------------ #
def test_get_project_inside_org_scope_ok() -> None:
    resp = _client().get("/api/v1/projects/CALM", headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 200
    assert resp.json()["project_key"] == "CALM"


def test_get_project_outside_org_scope_is_404() -> None:
    # bob may only see CALM -> RISKY is indistinguishable from missing.
    resp = _client().get("/api/v1/projects/RISKY", headers={"X-Org-Subject": "bob"})
    assert resp.status_code == 404


def test_get_project_no_org_headers_unchanged() -> None:
    resp = _client().get("/api/v1/projects/RISKY")
    assert resp.status_code == 200
