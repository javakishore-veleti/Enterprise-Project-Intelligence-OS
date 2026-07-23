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
from risk_analytics_api.services.forecast.forecasting import ForecastFacts, compute_forecast
from risk_analytics_api.services.forecast.subset import (
    FIELD_BY_SUBJECT,
    TINY_SUBSET,
    compute_subset_signals,
)

#: Reuse the delivery-forecasting agent's Admin-API config (model is read from here).
AGENT_KEY = "delivery_forecasting"

#: Confidence ceiling when the trajectory is too short to trust.
_LOW_DATA_CONFIDENCE = 0.35

#: Confidence ceiling for a thin (tiny) subject subset — even less trustworthy.
_TINY_SUBSET_CONFIDENCE = 0.2

#: Extra interval half-width added when a subject subset is tiny.
_TINY_SUBSET_WIDEN = 0.15
_TINY_MAX_HALFWIDTH = 0.49


def _widen_for_small_subset(facts: ForecastFacts, total: int) -> ForecastFacts:
    """Broaden the probability band on a tiny subject subset (thin evidence)."""
    if total >= TINY_SUBSET:
        return facts
    hw = min(_TINY_MAX_HALFWIDTH, facts.halfwidth + _TINY_SUBSET_WIDEN)
    p = facts.on_time_probability
    facts.probability_low = round(max(0.01, min(0.99, p - hw)), 3)
    facts.probability_high = round(max(0.01, min(0.99, p + hw)), 3)
    facts.halfwidth = round(hw, 3)
    return facts

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

    def _subset_signals(
        self, project_key: str, subject_type: str, subject_value: str
    ) -> tuple[list[dict], dict, int]:
        """Deterministic forecast inputs over the issue subset for a subject.

        Filters the evidence ``issues`` to those whose subject array
        (fix_versions / components / labels) contains ``subject_value``, pulls
        their status ``issue_histories``, and folds both into a single synthetic
        snapshot + project-counts dict that ``compute_forecast`` consumes like a
        one-point trajectory. Returns ``(history, project, subset_size)``.
        """
        db = self._mongo.db()
        field = FIELD_BY_SUBJECT[subject_type]
        issues = list(db["issues"].find(
            {"project_key": project_key, field: subject_value},
            {"_id": 0, "issue_key": 1, "status": 1, "priority": 1,
             "created_at": 1, "resolved_at": 1},
        ))
        keys = [i["issue_key"] for i in issues if i.get("issue_key")]
        histories: list[dict] = []
        if keys:
            histories = list(db["issue_histories"].find(
                {"project_key": project_key, "field": "status",
                 "issue_key": {"$in": keys}},
                {"_id": 0, "issue_key": 1, "to_value": 1, "author": 1},
            ))
        snapshot, project = compute_subset_signals(issues, histories)
        return [snapshot], project, len(issues)

    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        db = self._mongo.db()
        project = db["projects"].find_one({"project_key": request.project_key}, {"_id": 0})
        if project is None:
            raise NotFoundError(f"project '{request.project_key}' not found")

        subset_size: int | None = None
        if request.subject_type == "project":
            history = self._history(request.project_key)
            facts = compute_forecast(history, project)
        else:
            history, subset_project, subset_size = self._subset_signals(
                request.project_key, request.subject_type, request.subject_value)
            facts = compute_forecast(history, subset_project)
            facts = _widen_for_small_subset(facts, subset_size)
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
                subject_type=request.subject_type, subject_value=request.subject_value,
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
        if subset_size is not None and subset_size < TINY_SUBSET:
            confidence = min(confidence, _TINY_SUBSET_CONFIDENCE)

        _logger.info(
            "forecast completed",
            extra={"context": {"forecast_id": forecast_id, "run_id": run_id,
                               "project_key": request.project_key,
                               "subject_type": request.subject_type,
                               "subject_value": request.subject_value,
                               "on_time_probability": facts.on_time_probability,
                               "outlook": facts.outlook,
                               "trajectory_points": facts.trajectory_points}},
        )
        self._persist(ForecastRecord(
            forecast_id=forecast_id, project_key=request.project_key,
            subject_type=request.subject_type, subject_value=request.subject_value,
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
            forecast_id=forecast_id, project_key=request.project_key,
            subject_type=request.subject_type, subject_value=request.subject_value,
            question=None,
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
        self, scope: str | None, q: str | None, limit: int, offset: int,
        projects: list[str] | None = None,
    ) -> ForecastsPageResponse:
        if self._dao is None:
            return ForecastsPageResponse(
                total=0, returned=0, offset=offset, limit=limit, items=[])
        return self._dao.list_forecasts(scope, q, limit, offset, projects)

    def get_forecast(self, forecast_id: str) -> ForecastResponse:
        found = self._dao.get_forecast(forecast_id) if self._dao else None
        if found is None:
            raise NotFoundError(f"forecast '{forecast_id}' not found")
        return found
