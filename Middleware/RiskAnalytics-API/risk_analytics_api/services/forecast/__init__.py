"""Forecast service — deterministic forecast + grounded narration + persistence.

Wires the deterministic forecast math (``forecasting.compute_forecast`` over the
project's ``project_metrics`` trajectory) to the injected LLM narrator
(``graphs/forecast``), then maps the result onto the response DTO and persists it
to ``risk.forecasts`` (COMPLETED on success, FAILED if the narrator errors). The
persistence DAO is injected (optional): absent -> the forecast still returns
(graceful degradation) but is not persisted. The chat-model builder is injected so
tests run a fake (no model call); early-warning aside, the forecast needs a model.
"""
from __future__ import annotations

from typing import Any, Callable

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import NotFoundError
from risk_analytics_api.common.logging import get_logger
from risk_analytics_api.common.utilities import new_id, utc_now
from risk_analytics_api.daos.connection import MongoDatabaseFactory
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.requests import ForecastRequest
from risk_analytics_api.dtos.responses import (
    ForecastDriver,
    ForecastRecord,
    ForecastResponse,
    ForecastsPageResponse,
)
from risk_analytics_api.graphs.forecast import ForecastNarrator
from risk_analytics_api.interfaces.daos import (
    AgentConfigGateway,
    EvidenceDao,
    ForecastDao,
)
from risk_analytics_api.interfaces.services import ForecastService
from risk_analytics_api.services.forecast.forecasting import compute_forecast

#: Reuse the delivery-forecasting agent's Admin-API config (model is read from here).
AGENT_KEY = "delivery_forecasting"

#: Confidence ceiling when the trajectory is too short to trust.
_LOW_DATA_CONFIDENCE = 0.35

ChatModelBuilder = Callable[[str], Any]

_logger = get_logger(__name__)


def default_chat_model(model: str) -> Any:
    """Build the real Claude chat model (ANTHROPIC_API_KEY read from env by the SDK)."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, max_tokens=1500, timeout=90)


class DefaultForecastService(ForecastService):
    def __init__(
        self,
        mongo: MongoDatabaseFactory,
        evidence_dao: EvidenceDao,
        agent_config_gateway: AgentConfigGateway,
        settings: Settings,
        chat_model_builder: ChatModelBuilder = default_chat_model,
        forecasts_dao: ForecastDao | None = None,
    ) -> None:
        self._mongo = mongo
        self._evidence = evidence_dao
        self._config = agent_config_gateway
        self._settings = settings
        self._chat_model_builder = chat_model_builder
        self._dao = forecasts_dao

    def _resolve_model(self) -> str:
        cfg = self._config.get(AGENT_KEY)
        if cfg is None:
            return self._settings.default_agent_model
        _enabled, model, _framework = cfg
        return model or self._settings.default_agent_model

    def _persist(self, record: ForecastRecord) -> None:
        if self._dao is None:
            return
        try:
            self._dao.insert_forecast(record)
        except Exception:  # pragma: no cover - persistence must not break the run
            _logger.warning(
                "failed to persist forecast",
                extra={"context": {"forecast_id": record.forecast_id}},
            )

    def _history(self, project_key: str) -> list[dict]:
        cursor = (
            self._mongo.db()["project_metrics"]
            .find({"project_key": project_key}, {"_id": 0})
            .sort("computed_at", -1)
        )
        return list(cursor)

    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        db = self._mongo.db()
        project = db["projects"].find_one({"project_key": request.project_key}, {"_id": 0})
        if project is None:
            raise NotFoundError(f"project '{request.project_key}' not found")

        history = self._history(request.project_key)
        facts = compute_forecast(history, project)
        evidence = self._evidence.build_package(request.project_key)

        model = self._resolve_model()
        narrator = ForecastNarrator(self._chat_model_builder(model))

        forecast_id = new_id()
        run_id = new_id()
        created_at = utc_now()
        drivers = [ForecastDriver(**d) for d in facts.drivers]

        try:
            narration = narrator.run(facts, evidence)
        except Exception:
            self._persist(ForecastRecord(
                forecast_id=forecast_id, project_key=request.project_key,
                requested_by=request.requested_by, status=AnalysisStatus.FAILED.value,
                on_time_probability=facts.on_time_probability,
                probability_low=facts.probability_low, probability_high=facts.probability_high,
                projected_slip_days_low=facts.projected_slip_days_low,
                projected_slip_days_high=facts.projected_slip_days_high,
                outlook=facts.outlook, drivers=drivers, confidence=None,
                run_id=run_id, created_at=created_at,
            ))
            raise

        confidence = float(narration.confidence)
        if facts.trajectory_points < 2:
            confidence = min(confidence, _LOW_DATA_CONFIDENCE)

        _logger.info(
            "forecast completed",
            extra={"context": {"forecast_id": forecast_id, "run_id": run_id,
                               "project_key": request.project_key,
                               "on_time_probability": facts.on_time_probability,
                               "outlook": facts.outlook,
                               "trajectory_points": facts.trajectory_points}},
        )
        self._persist(ForecastRecord(
            forecast_id=forecast_id, project_key=request.project_key,
            requested_by=request.requested_by, status=AnalysisStatus.COMPLETED.value,
            on_time_probability=facts.on_time_probability,
            probability_low=facts.probability_low, probability_high=facts.probability_high,
            projected_slip_days_low=facts.projected_slip_days_low,
            projected_slip_days_high=facts.projected_slip_days_high,
            outlook=facts.outlook, drivers=drivers,
            bull_case=narration.bull_case, bear_case=narration.bear_case,
            would_change_mind=narration.would_change_mind, narrative=narration.narrative,
            confidence=confidence, run_id=run_id, created_at=created_at,
        ))
        return ForecastResponse(
            forecast_id=forecast_id, project_key=request.project_key, question=None,
            on_time_probability=facts.on_time_probability,
            probability_low=facts.probability_low, probability_high=facts.probability_high,
            projected_slip_days_low=facts.projected_slip_days_low,
            projected_slip_days_high=facts.projected_slip_days_high,
            outlook=facts.outlook, drivers=drivers,
            bull_case=narration.bull_case, bear_case=narration.bear_case,
            would_change_mind=narration.would_change_mind, narrative=narration.narrative,
            confidence=confidence, status=AnalysisStatus.COMPLETED.value,
            run_id=run_id, created_at=created_at,
        )

    def list_forecasts(
        self, scope: str | None, q: str | None, limit: int, offset: int
    ) -> ForecastsPageResponse:
        if self._dao is None:
            return ForecastsPageResponse(
                total=0, returned=0, offset=offset, limit=limit, items=[])
        return self._dao.list_forecasts(scope, q, limit, offset)

    def get_forecast(self, forecast_id: str) -> ForecastResponse:
        found = self._dao.get_forecast(forecast_id) if self._dao else None
        if found is None:
            raise NotFoundError(f"forecast '{forecast_id}' not found")
        return found
