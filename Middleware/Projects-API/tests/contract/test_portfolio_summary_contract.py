"""Contract tests for GET /api/v1/projects/portfolio-summary (fake DAO)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from projects_api.api.dependencies import provide_portfolio_summary_facade
from projects_api.api.main import create_app
from projects_api.dtos.common import PortfolioAggregate, PortfolioScoredRow
from projects_api.facades.portfolio_summary import PortfolioSummaryFacade
from projects_api.interfaces.daos import PortfolioSummaryDao, ProjectAssignmentsDao
from projects_api.services.portfolio_summary import DefaultPortfolioSummaryService

SCORED = [
    PortfolioScoredRow(project_key="RISKY", name="Risky Service", category="apache",
                       issue_count=1000, open_issue_count=1000, blocker_count=608,
                       reopen_rate=0.6, issue_aging_days=2067, critical_defect_ratio=0.9),
    PortfolioScoredRow(project_key="CALM", name="Calm Service", category=None,
                       issue_count=100, open_issue_count=2, blocker_count=0,
                       reopen_rate=0.0, issue_aging_days=5.0, critical_defect_ratio=0.0),
]
AGGREGATE = PortfolioAggregate(
    total_projects=4, total_issues=1100, total_open_issues=1002, scored=SCORED,
)

# user_key -> assigned project keys (the scoping seam).
ASSIGNMENTS = {"mgr-calm": ["CALM"]}


class _FakePortfolioDao(PortfolioSummaryDao):
    def portfolio_data(self, project_keys: list[str] | None = None) -> PortfolioAggregate:
        if project_keys is None:
            return AGGREGATE
        allowed = set(project_keys)
        scoped = [r for r in SCORED if r.project_key in allowed]
        return PortfolioAggregate(
            total_projects=len(scoped),
            total_issues=sum(r.issue_count for r in scoped),
            total_open_issues=sum(r.open_issue_count for r in scoped),
            scored=scoped,
        )


class _FakeAssignmentsDao(ProjectAssignmentsDao):
    def project_keys_for(self, user_key: str) -> list[str]:
        return list(ASSIGNMENTS.get(user_key, []))


def _client() -> TestClient:
    app = create_app()
    service = DefaultPortfolioSummaryService(_FakePortfolioDao())
    app.dependency_overrides[provide_portfolio_summary_facade] = (
        lambda: PortfolioSummaryFacade(service, _FakeAssignmentsDao())
    )
    return TestClient(app)


def test_portfolio_summary_full_shape_default_top() -> None:
    resp = _client().get("/api/v1/projects/portfolio-summary")
    assert resp.status_code == 200
    body = resp.json()

    # new top-level fields: scope, portfolio_score, computed_at
    assert body["scope"] == {"user_key": None, "project_count": 4, "scoped": False}
    assert 0.0 <= body["portfolio_score"] <= 100.0
    assert body["portfolio_score"] > 0.0
    assert isinstance(body["computed_at"], str) and body["computed_at"]

    # totals
    assert body["totals"] == {"projects": 4, "issues": 1100, "open_issues": 1002}

    # risk_bands: 2 scored (RISKY high, CALM low); 4 total -> 2 unscored
    assert set(body["risk_bands"]) == {"high", "medium", "low", "unscored"}
    assert body["risk_bands"]["unscored"] == 2
    assert body["risk_bands"]["high"] == 1
    assert body["risk_bands"]["low"] == 1

    assert body["overall_risk"] in {"Low", "Medium", "High"}
    assert body["overall_risk"] == "High"

    # top_projects: ranked descending, RISKY first, exact item field set
    keys = [p["project_key"] for p in body["top_projects"]]
    assert keys == ["RISKY", "CALM"]
    top = body["top_projects"][0]
    assert set(top) == {
        "project_key", "name", "category", "risk_score", "risk_band",
        "issue_count", "open_issue_count", "blocker_count", "reopen_rate",
        "issue_aging_days", "critical_defect_ratio", "headline",
    }
    assert top["risk_band"] == "High"
    assert 0.0 <= top["risk_score"] <= 100.0
    assert top["category"] == "apache"
    assert "608 blockers" in top["headline"]
    # nullable category survives the round trip
    assert body["top_projects"][1]["category"] is None


def test_portfolio_summary_custom_top() -> None:
    resp = _client().get("/api/v1/projects/portfolio-summary", params={"top": 1})
    assert resp.status_code == 200
    assert len(resp.json()["top_projects"]) == 1
    assert resp.json()["top_projects"][0]["project_key"] == "RISKY"


def test_portfolio_summary_top_too_large_is_422() -> None:
    assert _client().get(
        "/api/v1/projects/portfolio-summary", params={"top": 51}).status_code == 422


def test_portfolio_summary_top_too_small_is_422() -> None:
    assert _client().get(
        "/api/v1/projects/portfolio-summary", params={"top": 0}).status_code == 422


def test_portfolio_summary_route_not_shadowed_by_project_key() -> None:
    # the literal path must resolve to the summary endpoint, not GET /{project_key}
    body = _client().get("/api/v1/projects/portfolio-summary").json()
    assert "top_projects" in body and "totals" in body


def test_portfolio_summary_scoped_to_user_via_header() -> None:
    # mgr-calm is assigned only CALM -> summary scoped to that one project.
    resp = _client().get(
        "/api/v1/projects/portfolio-summary", headers={"X-User-Key": "mgr-calm"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["scope"] == {"user_key": "mgr-calm", "project_count": 1, "scoped": True}
    keys = [p["project_key"] for p in body["top_projects"]]
    assert keys == ["CALM"]
    assert "RISKY" not in keys
    assert body["totals"] == {"projects": 1, "issues": 100, "open_issues": 2}
    assert body["risk_bands"]["high"] == 0
    assert body["risk_bands"]["unscored"] == 0
    assert 0.0 <= body["portfolio_score"] <= 100.0


def test_portfolio_summary_unknown_user_falls_back_to_all() -> None:
    # a user with no assignments sees the whole portfolio (unscoped).
    resp = _client().get(
        "/api/v1/projects/portfolio-summary", headers={"X-User-Key": "nobody"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == {"user_key": "nobody", "project_count": 4, "scoped": False}
    assert [p["project_key"] for p in body["top_projects"]] == ["RISKY", "CALM"]


def test_portfolio_summary_default_top_is_15() -> None:
    # the `top` query param must default to 15 (per the enterprise design).
    schema = _client().get("/openapi.json").json()
    params = schema["paths"]["/api/v1/projects/portfolio-summary"]["get"]["parameters"]
    top_param = next(p for p in params if p["name"] == "top")
    assert top_param["schema"]["default"] == 15
    assert top_param["schema"]["minimum"] == 1
    assert top_param["schema"]["maximum"] == 50
