"""Analysis orchestration service.

Coordinates one analysis run: build deterministic evidence, then for each
requested agent read its Admin-API config (enabled/model/framework), build the
agent via the framework toggle, run it, and persist the findings. The agent
factory is injected so this is unit-testable without any model call.
"""
from __future__ import annotations

from typing import Callable

from agent_core import RiskAgent

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import AgentExecutionError, NotFoundError
from risk_analytics_api.common.logging import get_logger
from risk_analytics_api.common.utilities import new_id, utc_now
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.requests import StartAnalysisRequest
from risk_analytics_api.dtos.responses import AnalysisRunResponse
from risk_analytics_api.interfaces.daos import (
    AgentConfigGateway,
    GraphRunDao,
    RiskFindingDao,
)
from risk_analytics_api.interfaces.services import (
    AnalysisOrchestrationService,
    EvidenceRetrievalService,
)

# (agent_key, framework, model) -> RiskAgent, or None if the agent_key is not implemented.
AgentFactory = Callable[[str, str, str], "RiskAgent | None"]

_logger = get_logger(__name__)


class DefaultAnalysisOrchestrationService(AnalysisOrchestrationService):
    def __init__(
        self,
        evidence_service: EvidenceRetrievalService,
        agent_config_gateway: AgentConfigGateway,
        graph_run_dao: GraphRunDao,
        risk_finding_dao: RiskFindingDao,
        agent_factory: AgentFactory,
        settings: Settings,
    ) -> None:
        self._evidence = evidence_service
        self._config = agent_config_gateway
        self._runs = graph_run_dao
        self._findings = risk_finding_dao
        self._factory = agent_factory
        self._settings = settings

    def run(self, project_key: str, request: StartAnalysisRequest) -> AnalysisRunResponse:
        # Build evidence first so a missing project fails cleanly (no dangling run).
        evidence = self._evidence.for_project(project_key)

        run_id = new_id()
        started = utc_now()
        self._runs.create(run_id, project_key, request.agents, started)

        try:
            for agent_key in request.agents:
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

                agent = self._factory(agent_key, framework, model)
                if agent is None:
                    _logger.info("agent not implemented, skipping", extra={"context": {"agent_key": agent_key}})
                    continue

                findings = agent.analyze(evidence)
                self._findings.add_many(run_id, project_key, findings)
                _logger.info(
                    "agent produced findings",
                    extra={"context": {"agent_key": agent_key, "framework": framework,
                                       "model": model, "count": len(findings)}},
                )
        except Exception as exc:
            self._runs.complete(run_id, AnalysisStatus.FAILED.value, utc_now())
            raise AgentExecutionError(f"analysis failed: {exc}") from exc

        self._runs.complete(run_id, AnalysisStatus.COMPLETED.value, utc_now())
        return self._runs.get(run_id)

    def get_run(self, run_id: str) -> AnalysisRunResponse:
        run = self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"analysis run '{run_id}' not found")
        return run
