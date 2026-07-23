"""Scenario service — deterministic re-forecast + cascade + narration + persistence.

Wires the deterministic scenario mechanics (base forecast, keyword-driven effect,
dependency + shared-contributor cascade propagation — all in ``cascade`` and
``forecasting``) to the injected LLM narrator (``graphs/scenario``), maps the
result onto the DTO, and persists it to ``risk.scenarios`` (COMPLETED on success,
FAILED if the narrator errors). Persistence DAO injected (optional): absent ->
still returns, not persisted. Chat model injected so tests run a fake.
"""
from __future__ import annotations

from typing import Any, Callable

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.common.logging import get_logger
from risk_analytics_api.common.utilities import new_id, utc_now
from risk_analytics_api.daos.connection import MongoDatabaseFactory
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.requests import ScenarioRequest
from risk_analytics_api.dtos.responses import (
    ScenarioCascade,
    ScenarioRecord,
    ScenarioResponse,
    ScenariosPageResponse,
)
from risk_analytics_api.graphs.scenario import ScenarioNarrator, format_facts
from risk_analytics_api.interfaces.daos import AgentConfigGateway, ScenarioDao
from risk_analytics_api.interfaces.services import ScenarioService
from risk_analytics_api.services.forecast.forecasting import (
    _clamp,
    compute_forecast,
    slip_center,
)
from risk_analytics_api.services.scenario import cascade as cascade_logic

#: Reuse the delivery-forecasting agent's Admin-API config (model is read from here).
AGENT_KEY = "delivery_forecasting"
_LOW_DATA_CONFIDENCE = 0.4

ChatModelBuilder = Callable[[str], Any]

_logger = get_logger(__name__)


def default_chat_model(model: str) -> Any:
    """Build the real Claude chat model (ANTHROPIC_API_KEY read from env by the SDK)."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, max_tokens=1500, timeout=90)


class DefaultScenarioService(ScenarioService):
    def __init__(
        self,
        mongo: MongoDatabaseFactory,
        agent_config_gateway: AgentConfigGateway,
        settings: Settings,
        chat_model_builder: ChatModelBuilder = default_chat_model,
        scenarios_dao: ScenarioDao | None = None,
    ) -> None:
        self._mongo = mongo
        self._config = agent_config_gateway
        self._settings = settings
        self._chat_model_builder = chat_model_builder
        self._dao = scenarios_dao

    def _resolve_model(self) -> str:
        cfg = self._config.get(AGENT_KEY)
        if cfg is None:
            return self._settings.default_agent_model
        _enabled, model, _framework = cfg
        return model or self._settings.default_agent_model

    def _persist(self, record: ScenarioRecord) -> None:
        if self._dao is None:
            return
        try:
            self._dao.insert_scenario(record)
        except Exception:  # pragma: no cover - persistence must not break the run
            _logger.warning(
                "failed to persist scenario",
                extra={"context": {"scenario_id": record.scenario_id}},
            )

    def _history(self, project_key: str) -> list[dict]:
        cursor = (
            self._mongo.db()["project_metrics"]
            .find({"project_key": project_key}, {"_id": 0})
            .sort("computed_at", -1)
        )
        return list(cursor)

    def simulate(self, request: ScenarioRequest) -> ScenarioResponse:
        db = self._mongo.db()
        project = db["projects"].find_one({"project_key": request.project_key}, {"_id": 0})
        if project is None:
            raise NotFoundError(f"project '{request.project_key}' not found")

        history = self._history(request.project_key)
        latest = history[0] if history else {}
        facts = compute_forecast(history, project)

        base_p = facts.on_time_probability
        effect = cascade_logic.estimate_scenario_effect(request.scenario)
        projected_p = round(_clamp(base_p + effect, 0.02, 0.98), 3)
        probability_delta = round(projected_p - base_p, 3)

        base_slip = int(round(slip_center(base_p, latest, project)))
        projected_slip = int(round(slip_center(projected_p, latest, project)))

        cascades_raw = cascade_logic.find_cascades(db, request.project_key)
        cascades = [ScenarioCascade(**c) for c in cascades_raw]
        portfolio_delta = cascade_logic.portfolio_risk_delta(probability_delta, cascades_raw)

        model = self._resolve_model()
        narrator = ScenarioNarrator(self._chat_model_builder(model))
        facts_block = format_facts(
            base_p, projected_p, base_slip, projected_slip, portfolio_delta, cascades_raw)

        scenario_id = new_id()
        run_id = new_id()
        created_at = utc_now()

        try:
            narration = narrator.run(request.scenario, facts_block)
        except Exception:
            self._persist(ScenarioRecord(
                scenario_id=scenario_id, project_key=request.project_key,
                requested_by=request.requested_by, scenario=request.scenario,
                status=AnalysisStatus.FAILED.value,
                base_on_time_probability=base_p, projected_on_time_probability=projected_p,
                probability_delta=probability_delta, base_slip_days=base_slip,
                projected_slip_days=projected_slip, portfolio_risk_delta=portfolio_delta,
                cascades=cascades, confidence=None, run_id=run_id, created_at=created_at,
            ))
            raise

        confidence = float(narration.confidence)
        if facts.trajectory_points < 2:
            confidence = min(confidence, _LOW_DATA_CONFIDENCE)

        _logger.info(
            "scenario completed",
            extra={"context": {"scenario_id": scenario_id, "run_id": run_id,
                               "project_key": request.project_key,
                               "probability_delta": probability_delta,
                               "cascades": len(cascades)}},
        )
        self._persist(ScenarioRecord(
            scenario_id=scenario_id, project_key=request.project_key,
            requested_by=request.requested_by, scenario=request.scenario,
            status=AnalysisStatus.COMPLETED.value,
            base_on_time_probability=base_p, projected_on_time_probability=projected_p,
            probability_delta=probability_delta, base_slip_days=base_slip,
            projected_slip_days=projected_slip, portfolio_risk_delta=portfolio_delta,
            cascades=cascades, narrative=narration.narrative, confidence=confidence,
            run_id=run_id, created_at=created_at,
        ))
        return ScenarioResponse(
            scenario_id=scenario_id, project_key=request.project_key,
            scenario=request.scenario,
            base_on_time_probability=base_p, projected_on_time_probability=projected_p,
            probability_delta=probability_delta, base_slip_days=base_slip,
            projected_slip_days=projected_slip, portfolio_risk_delta=portfolio_delta,
            cascades=cascades, narrative=narration.narrative, confidence=confidence,
            status=AnalysisStatus.COMPLETED.value, run_id=run_id, created_at=created_at,
        )

    def list_scenarios(
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> ScenariosPageResponse:
        if self._dao is None:
            return ScenariosPageResponse(
                total=0, returned=0, offset=offset, limit=limit, items=[])
        return self._dao.list_scenarios(scope, q, limit, offset, projects)

    def get_scenario(self, scenario_id: str) -> ScenarioResponse:
        found = self._dao.get_scenario(scenario_id) if self._dao else None
        if found is None:
            raise NotFoundError(f"scenario '{scenario_id}' not found")
        return found
