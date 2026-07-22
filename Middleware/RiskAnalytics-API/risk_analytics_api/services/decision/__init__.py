"""Decision service — Options-first prescriptive decision support + persistence.

Decide answers "what should we do?" and LEADS WITH OPTIONS. This service wires the
deterministic evidence the forecast/investigation use (the delivery forecast over
the ``project_metrics`` trajectory, the open blockers, and the top contributors —
all pure Python, NO LLM) to the injected LLM options agent (``graphs/decision``,
reusing the ``mitigation_planning`` persona), then maps the 2-3 generated options
onto the response DTO and persists the decision to ``risk.decisions``.

Lifecycle: ``run_decision`` persists DRAFTED (FAILED + re-raise if the agent
errors); ``select_option`` sets the chosen option (status SELECTED — its actions +
owners ARE the plan); ``approve_decision`` records approval (status APPROVED) as a
**dry-run / preview only** — it never calls an external system or creates real
tickets (real ticket creation is a future gated integration). The persistence DAO
is injected (optional): absent -> ``run_decision`` still returns (graceful
degradation), but select/approve/list/get require it. The chat-model builder is
injected so tests run a fake (no model call).
"""
from __future__ import annotations

from typing import Any, Callable

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError, ValidationError
from risk_analytics_api.common.logging import get_logger
from risk_analytics_api.common.utilities import new_id, utc_now
from risk_analytics_api.daos.connection import MongoDatabaseFactory
from risk_analytics_api.dtos.requests import DecisionRequest, SelectOptionRequest
from risk_analytics_api.dtos.responses import (
    DecisionOption,
    DecisionRecord,
    DecisionResponse,
    DecisionsPageResponse,
)
from risk_analytics_api.graphs.decision import MAX_OPTIONS, DecisionOptionsAgent
from risk_analytics_api.interfaces.daos import (
    AgentConfigGateway,
    DecisionDao,
    EvidenceDao,
)
from risk_analytics_api.interfaces.services import DecisionService
from risk_analytics_api.services.forecast.forecasting import compute_forecast

#: Reuse the mitigation-planning agent's Admin-API config (model is read from here).
AGENT_KEY = "mitigation_planning"

#: Confidence ceiling when the trajectory is too short to trust.
_LOW_DATA_CONFIDENCE = 0.35
#: How many contributors to surface as candidate owners.
_TOP_CONTRIBUTORS = 5
#: Statuses (Decide's own lifecycle — not the RUNNING/COMPLETED analysis states).
_DRAFTED, _SELECTED, _APPROVED, _FAILED = "DRAFTED", "SELECTED", "APPROVED", "FAILED"

ChatModelBuilder = Callable[[str], Any]

_logger = get_logger(__name__)


def default_chat_model(model: str) -> Any:
    """Build the real Claude chat model (ANTHROPIC_API_KEY read from env by the SDK)."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, max_tokens=2000, timeout=90)


def top_contributors(db: Any, project_key: str, limit: int = _TOP_CONTRIBUTORS) -> list[str]:
    """The project's most active contributors (history authorship, most active first).

    Deterministic + bounded: distinct authors, ranked by their history-event count.
    These become the candidate ``suggested_owners`` the options agent draws from.
    """
    authors = [
        a for a in db["issue_histories"].distinct("author", {"project_key": project_key}) if a
    ]
    ranked = sorted(
        authors,
        key=lambda a: (
            -db["issue_histories"].count_documents({"project_key": project_key, "author": a}),
            a,
        ),
    )
    return ranked[:limit]


class DefaultDecisionService(DecisionService):
    def __init__(
        self,
        mongo: MongoDatabaseFactory,
        evidence_dao: EvidenceDao,
        agent_config_gateway: AgentConfigGateway,
        settings: Settings,
        chat_model_builder: ChatModelBuilder = default_chat_model,
        decisions_dao: DecisionDao | None = None,
    ) -> None:
        self._mongo = mongo
        self._evidence = evidence_dao
        self._config = agent_config_gateway
        self._settings = settings
        self._chat_model_builder = chat_model_builder
        self._dao = decisions_dao

    def _resolve_model(self) -> str:
        cfg = self._config.get(AGENT_KEY)
        if cfg is None:
            return self._settings.default_agent_model
        _enabled, model, _framework = cfg
        return model or self._settings.default_agent_model

    def _persist(self, record: DecisionRecord) -> None:
        if self._dao is None:
            return
        try:
            self._dao.insert_decision(record)
        except Exception:  # pragma: no cover - persistence must not break the run
            _logger.warning(
                "failed to persist decision",
                extra={"context": {"decision_id": record.decision_id}},
            )

    def _history(self, project_key: str) -> list[dict]:
        cursor = (
            self._mongo.db()["project_metrics"]
            .find({"project_key": project_key}, {"_id": 0})
            .sort("computed_at", -1)
        )
        return list(cursor)

    def decide(self, request: DecisionRequest) -> DecisionResponse:
        db = self._mongo.db()
        project = db["projects"].find_one({"project_key": request.project_key}, {"_id": 0})
        if project is None:
            raise NotFoundError(f"project '{request.project_key}' not found")

        history = self._history(request.project_key)
        facts = compute_forecast(history, project)
        evidence = self._evidence.build_package(request.project_key)
        owners = top_contributors(db, request.project_key)

        model = self._resolve_model()
        agent = DecisionOptionsAgent(self._chat_model_builder(model))

        decision_id = new_id()
        run_id = new_id()
        created_at = utc_now()

        try:
            result = agent.run(facts, evidence, owners, request.context)
        except Exception:
            self._persist(DecisionRecord(
                decision_id=decision_id, project_key=request.project_key,
                requested_by=request.requested_by, status=_FAILED,
                options=[], selected_option_id=None, narrative="", confidence=None,
                run_id=run_id, created_at=created_at, approved_at=None,
            ))
            raise

        options = self._assign_options(result.options, owners)
        confidence = float(result.confidence)
        if facts.trajectory_points < 2:
            confidence = min(confidence, _LOW_DATA_CONFIDENCE)

        _logger.info(
            "decision drafted",
            extra={"context": {"decision_id": decision_id, "run_id": run_id,
                               "project_key": request.project_key,
                               "options": len(options),
                               "trajectory_points": facts.trajectory_points}},
        )
        self._persist(DecisionRecord(
            decision_id=decision_id, project_key=request.project_key,
            requested_by=request.requested_by, status=_DRAFTED,
            options=options, selected_option_id=None, narrative=result.narrative,
            confidence=confidence, run_id=run_id, created_at=created_at, approved_at=None,
        ))
        return DecisionResponse(
            decision_id=decision_id, project_key=request.project_key, question=None,
            options=options, selected_option_id=None, status=_DRAFTED,
            narrative=result.narrative, confidence=confidence,
            run_id=run_id, created_at=created_at, approved_at=None,
        )

    def _assign_options(self, raw: list, owners: list[str]) -> list[DecisionOption]:
        """Assign stable option ids + ground suggested_owners in the top contributors."""
        options: list[DecisionOption] = []
        for i, o in enumerate(raw[:MAX_OPTIONS], start=1):
            suggested = list(getattr(o, "suggested_owners", []) or []) or owners[:2]
            options.append(DecisionOption(
                option_id=f"opt-{i}",
                title=o.title or f"Option {i}",
                summary=o.summary,
                actions=list(o.actions),
                suggested_owners=suggested,
                predicted_outcome=o.predicted_outcome,
                tradeoffs=o.tradeoffs,
                recovery_estimate=o.recovery_estimate,
                confidence=float(o.confidence),
            ))
        return options

    def select_option(self, decision_id: str, request: SelectOptionRequest) -> DecisionResponse:
        decision = self._require(decision_id)
        if request.option_id not in {o.option_id for o in decision.options}:
            raise ValidationError(
                f"option '{request.option_id}' is not one of this decision's options")
        self._dao.update_selection(decision_id, request.option_id, _SELECTED)
        return self._require(decision_id)

    def approve_decision(self, decision_id: str) -> DecisionResponse:
        # Dry-run / preview only: records approval; it does NOT call any external
        # system or create real tickets. Real ticket creation is a future gated
        # integration.
        self._require(decision_id)
        self._dao.update_approval(decision_id, _APPROVED, utc_now())
        return self._require(decision_id)

    def _require(self, decision_id: str) -> DecisionResponse:
        found = self._dao.get_decision(decision_id) if self._dao else None
        if found is None:
            raise NotFoundError(f"decision '{decision_id}' not found")
        return found

    def list_decisions(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> DecisionsPageResponse:
        if self._dao is None:
            return DecisionsPageResponse(
                total=0, returned=0, offset=offset, limit=limit, items=[])
        return self._dao.list_decisions(scope, q, limit, offset)

    def get_decision(self, decision_id: str) -> DecisionResponse:
        return self._require(decision_id)
