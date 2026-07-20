"""Analysis orchestration service.

Coordinates one analysis run: build deterministic evidence, then for each
requested agent read its Admin-API config (enabled/model/framework), build the
agent via the framework toggle, run it, and persist the findings. The agent
factory is injected so this is unit-testable without any model call.
"""
from __future__ import annotations

from typing import Callable

from agent_core import EvidenceMetrics, EvidencePackage, RiskAgent, ReviewContext

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import AgentExecutionError, NotFoundError
from risk_analytics_api.common.logging import get_logger
from risk_analytics_api.common.utilities import new_id, utc_now
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.requests import StartAnalysisRequest, StartPortfolioAnalysisRequest
from risk_analytics_api.dtos.responses import AnalysisRunListResponse, AnalysisRunResponse
from risk_analytics_api.interfaces.daos import (
    AgentConfigGateway,
    GraphRunDao,
    ReportDao,
    RiskFindingDao,
)
from risk_analytics_api.graphs.project_risk_manager import ProjectRiskManager
from risk_analytics_api.graphs.risk_review import ProjectRiskReview, build_review
from risk_analytics_api.interfaces.services import (
    AnalysisOrchestrationService,
    EvidenceRetrievalService,
)

# (agent_key, framework, model) -> RiskAgent, or None if the agent_key is not implemented.
AgentFactory = Callable[[str, str, str], "RiskAgent | None"]
# config_get, default_model -> ProjectRiskReview
ReviewBuilder = Callable[..., ProjectRiskReview]

_logger = get_logger(__name__)


class DefaultAnalysisOrchestrationService(AnalysisOrchestrationService):
    def __init__(
        self,
        evidence_service: EvidenceRetrievalService,
        agent_config_gateway: AgentConfigGateway,
        graph_run_dao: GraphRunDao,
        risk_finding_dao: RiskFindingDao,
        report_dao: ReportDao,
        agent_factory: AgentFactory,
        settings: Settings,
        review_builder: ReviewBuilder = build_review,
    ) -> None:
        self._evidence = evidence_service
        self._config = agent_config_gateway
        self._runs = graph_run_dao
        self._findings = risk_finding_dao
        self._reports = report_dao
        self._factory = agent_factory
        self._manager = ProjectRiskManager(agent_factory)
        self._settings = settings
        self._review_builder = review_builder

    def _resolve_specs(self, agent_keys: list[str]) -> list[tuple[str, str, str]]:
        """Resolve each requested agent's (key, framework, model) from Admin config."""
        specs: list[tuple[str, str, str]] = []
        for agent_key in agent_keys:
            cfg = self._config.get(agent_key)
            if cfg is None:
                enabled = True
                model = self._settings.default_agent_model
                framework = self._settings.default_agent_framework
            else:
                enabled, model, framework = cfg
            if not enabled:
                _logger.info("agent disabled, skipping", extra={"context": {"agent_key": agent_key}})
                continue
            specs.append((agent_key, framework, model))
        return specs

    def run(self, project_key: str, request: StartAnalysisRequest) -> AnalysisRunResponse:
        # Build evidence first so a missing project fails cleanly (no dangling run).
        evidence = self._evidence.for_project(project_key)
        specs = self._resolve_specs(request.agents)

        run_id = new_id()
        started = utc_now()
        self._runs.create(run_id, project_key, request.agents, started)

        # Fan out across specialists via the LangGraph manager graph.
        result = self._manager.run(evidence, specs)
        for err in result.errors:
            _logger.warning("agent failed", extra={"context": err})

        # Fail the run only if every attempted agent errored and produced nothing.
        if result.errors and not result.findings:
            self._runs.complete(run_id, AnalysisStatus.FAILED.value, utc_now())
            raise AgentExecutionError(
                "analysis failed: " + "; ".join(e.get("error", "") for e in result.errors)
            )

        findings = result.findings
        n_reports = 0
        # Optionally run the review pipeline (validate/dedup/correlate/score/critic + reports).
        if request.include_review and findings:
            review = self._review_builder(self._config.get, self._settings.default_agent_model)
            review_result = review.run(
                ReviewContext(
                    project_key=project_key,
                    project_name=evidence.project_name,
                    evidence=evidence,
                    findings=findings,
                )
            )
            findings = review_result.findings
            if review_result.reports:
                self._reports.add_many(run_id, project_key, review_result.reports)
                n_reports = len(review_result.reports)

        if findings:
            self._findings.add_many(run_id, project_key, findings)

        self._runs.complete(run_id, AnalysisStatus.COMPLETED.value, utc_now())
        _logger.info(
            "analysis completed",
            extra={"context": {"run_id": run_id, "agents": [s[0] for s in specs],
                               "findings": len(findings), "reports": n_reports,
                               "reviewed": request.include_review, "errors": len(result.errors)}},
        )
        return self._runs.get(run_id)

    #: Max projects a portfolio run resolves from the evidence store when none given.
    PORTFOLIO_LIMIT = 25

    def run_portfolio(
        self, portfolio_key: str, request: StartPortfolioAnalysisRequest
    ) -> AnalysisRunResponse:
        project_keys = request.project_keys or self._evidence.list_project_keys(self.PORTFOLIO_LIMIT)

        run_id = new_id()
        started = utc_now()
        self._runs.create(run_id, portfolio_key, request.agents, started)

        specs = self._resolve_specs(request.agents)
        aggregate: list = []
        analyzed = 0
        for project_key in project_keys:
            try:
                evidence = self._evidence.for_project(project_key)
            except NotFoundError:
                continue
            result = self._manager.run(evidence, specs)
            aggregate.extend(result.findings)
            analyzed += 1

        # Portfolio synthesis: cross-project dedup/correlation/scoring + reports.
        # Per-finding evidence_validation and critic are skipped (they need each
        # finding's own project evidence, which isn't in the aggregate context).
        def _portfolio_config(agent_key: str):
            if agent_key in ("evidence_validation", "critic"):
                return (False, self._settings.default_agent_model, "langgraph")
            return self._config.get(agent_key)

        review = self._review_builder(_portfolio_config, self._settings.default_agent_model)
        synth_evidence = EvidencePackage(
            project_key=portfolio_key,
            project_name=f"Portfolio {portfolio_key}",
            metrics=EvidenceMetrics(),
            observations=[f"{analyzed} projects analyzed", f"{len(aggregate)} findings aggregated"],
        )
        review_result = review.run(
            ReviewContext(
                project_key=portfolio_key, project_name=f"Portfolio {portfolio_key}",
                evidence=synth_evidence, findings=aggregate,
            )
        )
        if review_result.findings:
            self._findings.add_many(run_id, portfolio_key, review_result.findings)
        if review_result.reports:
            self._reports.add_many(run_id, portfolio_key, review_result.reports)

        self._runs.complete(run_id, AnalysisStatus.COMPLETED.value, utc_now())
        _logger.info(
            "portfolio analysis completed",
            extra={"context": {"run_id": run_id, "portfolio_key": portfolio_key,
                               "projects": analyzed, "findings": len(review_result.findings)}},
        )
        return self._runs.get(run_id).model_copy(update={"project_count": analyzed})

    def get_run(self, run_id: str) -> AnalysisRunResponse:
        run = self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"analysis run '{run_id}' not found")
        return run

    def list_runs(self, project_key: str, limit: int) -> AnalysisRunListResponse:
        return AnalysisRunListResponse(
            project_key=project_key, runs=self._runs.list_for_project(project_key, limit))
