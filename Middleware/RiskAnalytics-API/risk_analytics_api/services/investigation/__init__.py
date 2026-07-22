"""Investigation service — builds the evidence tools + runs the Investigation Agent.

This is the layer that wires the deterministic evidence-store tools (over the
Mongo handle, scoped to one project) to the injected LLM and the LangGraph
tool-calling loop, then maps the agent's framework-free result onto the response
DTO. The chat-model builder is injected so tests run a fake LLM (no model call).
"""
from __future__ import annotations

from typing import Any, Callable

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.common.logging import get_logger
from risk_analytics_api.common.utilities import new_id, utc_now
from risk_analytics_api.daos.connection import MongoDatabaseFactory
from risk_analytics_api.dtos.requests import InvestigateRequest
from risk_analytics_api.dtos.responses import (
    EvidenceCitation,
    InvestigationResponse,
    InvestigationStep,
)
from risk_analytics_api.graphs.investigation import (
    DEFAULT_MAX_ITERATIONS,
    InvestigationAgent,
)
from risk_analytics_api.graphs.investigation.tools import build_investigation_tools
from risk_analytics_api.interfaces.daos import AgentConfigGateway
from risk_analytics_api.interfaces.services import InvestigationService

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
    ) -> None:
        self._mongo = mongo
        self._config = agent_config_gateway
        self._settings = settings
        self._chat_model_builder = chat_model_builder
        self._max_iterations = max_iterations

    def _resolve_model(self) -> str:
        cfg = self._config.get(AGENT_KEY)
        if cfg is None:
            return self._settings.default_agent_model
        _enabled, model, _framework = cfg
        return model or self._settings.default_agent_model

    def investigate(self, request: InvestigateRequest) -> InvestigationResponse:
        db = self._mongo.db()
        # Fail cleanly on an unknown project (same invariant as evidence retrieval).
        if db["projects"].find_one({"project_key": request.project_key}, {"_id": 0}) is None:
            raise NotFoundError(f"project '{request.project_key}' not found")

        model = self._resolve_model()
        tools = build_investigation_tools(db, request.project_key)
        agent = InvestigationAgent(
            self._chat_model_builder(model), tools, max_iterations=self._max_iterations
        )
        result = agent.run(request.project_key, request.question)

        run_id = new_id()
        _logger.info(
            "investigation completed",
            extra={"context": {"run_id": run_id, "project_key": request.project_key,
                               "steps": len(result.steps), "confidence": result.confidence}},
        )
        return InvestigationResponse(
            project_key=request.project_key,
            question=request.question,
            hypotheses=result.hypotheses,
            steps=[InvestigationStep(**s) for s in result.steps],
            root_cause=result.root_cause,
            causal_chain=result.causal_chain,
            confidence=result.confidence,
            evidence=[EvidenceCitation(**e) for e in result.evidence],
            recommended_action=result.recommended_action,
            run_id=run_id,
            generated_at=utc_now(),
        )
