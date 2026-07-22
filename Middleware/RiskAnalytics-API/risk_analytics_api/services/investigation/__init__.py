"""Investigation service — builds the evidence tools + runs the Investigation Agent.

This is the layer that wires the deterministic evidence-store tools (over the
Mongo handle, scoped to one project) to the injected LLM and the LangGraph
tool-calling loop, then maps the agent's framework-free result onto the response
DTO. The chat-model builder is injected so tests run a fake LLM (no model call).

It also owns investigation **persistence + history + templates**: each run is
assigned an ``investigation_id`` up front and written to ``risk.investigations``
(COMPLETED on success, FAILED if the agent errors), and the service exposes the
history list, a single-investigation fetch, and the template registry. The
persistence DAO is injected (optional): when absent, runs still return their
result (graceful degradation) but are not persisted.
"""
from __future__ import annotations

from typing import Any, Callable

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.common.logging import get_logger
from risk_analytics_api.common.utilities import new_id, utc_now
from risk_analytics_api.daos.connection import MongoDatabaseFactory
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.requests import InvestigateRequest
from risk_analytics_api.dtos.responses import (
    EvidenceCitation,
    InvestigationRecord,
    InvestigationResponse,
    InvestigationsPageResponse,
    InvestigationStep,
    InvestigationTemplateResponse,
)
from risk_analytics_api.graphs.investigation import (
    DEFAULT_MAX_ITERATIONS,
    InvestigationAgent,
)
from risk_analytics_api.graphs.investigation.tools import build_investigation_tools
from risk_analytics_api.interfaces.daos import AgentConfigGateway, InvestigationDao
from risk_analytics_api.interfaces.services import InvestigationService
from risk_analytics_api.services.investigation import templates as template_registry

#: Admin-API agent config key for the Investigation Agent (model is read from here).
AGENT_KEY = "investigation"

# model_name -> chat model (supports bind_tools + with_structured_output).
ChatModelBuilder = Callable[[str], Any]

_logger = get_logger(__name__)


def default_chat_model(model: str) -> Any:
    """Build the real Claude chat model (ANTHROPIC_API_KEY read from the env by the SDK)."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, max_tokens=2000, timeout=90)


class DefaultInvestigationService(InvestigationService):
    def __init__(
        self,
        mongo: MongoDatabaseFactory,
        agent_config_gateway: AgentConfigGateway,
        settings: Settings,
        chat_model_builder: ChatModelBuilder = default_chat_model,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        investigations_dao: InvestigationDao | None = None,
    ) -> None:
        self._mongo = mongo
        self._config = agent_config_gateway
        self._settings = settings
        self._chat_model_builder = chat_model_builder
        self._max_iterations = max_iterations
        self._dao = investigations_dao

    def _resolve_model(self) -> str:
        cfg = self._config.get(AGENT_KEY)
        if cfg is None:
            return self._settings.default_agent_model
        _enabled, model, _framework = cfg
        return model or self._settings.default_agent_model

    def _persist(self, record: InvestigationRecord) -> None:
        """Best-effort persistence: skip when no DAO is wired; never lose the result."""
        if self._dao is None:
            return
        try:
            self._dao.insert_investigation(record)
        except Exception:  # pragma: no cover - persistence must not break the run
            _logger.warning(
                "failed to persist investigation",
                extra={"context": {"investigation_id": record.investigation_id}},
            )

    def investigate(self, request: InvestigateRequest) -> InvestigationResponse:
        db = self._mongo.db()
        # Fail cleanly on an unknown project (same invariant as evidence retrieval).
        if db["projects"].find_one({"project_key": request.project_key}, {"_id": 0}) is None:
            raise NotFoundError(f"project '{request.project_key}' not found")

        template = template_registry.resolve_template(request.template_key)
        model = self._resolve_model()
        tools = build_investigation_tools(db, request.project_key)
        agent = InvestigationAgent(
            self._chat_model_builder(model), tools, max_iterations=self._max_iterations
        )

        # IDs assigned before running so a failed run is still persisted (FAILED).
        investigation_id = new_id()
        run_id = new_id()
        created_at = utc_now()

        try:
            result = agent.run(
                request.project_key,
                request.question,
                emphasis=template_registry.emphasis_for(template),
            )
        except Exception:
            self._persist(InvestigationRecord(
                investigation_id=investigation_id, project_key=request.project_key,
                requested_by=request.requested_by, question=request.question,
                template_key=template.template_key, status=AnalysisStatus.FAILED.value,
                root_cause="", confidence=None, recommended_action="",
                run_id=run_id, created_at=created_at,
            ))
            raise

        _logger.info(
            "investigation completed",
            extra={"context": {"investigation_id": investigation_id, "run_id": run_id,
                               "project_key": request.project_key, "template": template.template_key,
                               "steps": len(result.steps), "confidence": result.confidence}},
        )
        steps = [InvestigationStep(**s) for s in result.steps]
        evidence = [EvidenceCitation(**e) for e in result.evidence]
        self._persist(InvestigationRecord(
            investigation_id=investigation_id, project_key=request.project_key,
            requested_by=request.requested_by, question=request.question,
            template_key=template.template_key, status=AnalysisStatus.COMPLETED.value,
            root_cause=result.root_cause, confidence=result.confidence,
            recommended_action=result.recommended_action, hypotheses=result.hypotheses,
            causal_chain=result.causal_chain, steps=steps, evidence=evidence,
            run_id=run_id, created_at=created_at,
        ))
        return InvestigationResponse(
            investigation_id=investigation_id,
            project_key=request.project_key,
            question=request.question,
            template_key=template.template_key,
            status=AnalysisStatus.COMPLETED.value,
            hypotheses=result.hypotheses,
            steps=steps,
            root_cause=result.root_cause,
            causal_chain=result.causal_chain,
            confidence=result.confidence,
            evidence=evidence,
            recommended_action=result.recommended_action,
            run_id=run_id,
            generated_at=created_at,
        )

    def list_investigations(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> InvestigationsPageResponse:
        if self._dao is None:
            return InvestigationsPageResponse(
                total=0, returned=0, offset=offset, limit=limit, items=[])
        return self._dao.list_investigations(scope, q, limit, offset)

    def get_investigation(self, investigation_id: str) -> InvestigationResponse:
        found = self._dao.get_investigation(investigation_id) if self._dao else None
        if found is None:
            raise NotFoundError(f"investigation '{investigation_id}' not found")
        return found

    def list_templates(self) -> list[InvestigationTemplateResponse]:
        return template_registry.list_templates()
