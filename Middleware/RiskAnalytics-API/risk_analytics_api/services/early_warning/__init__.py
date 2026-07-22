"""Early-warning service — computed on read (NO LLM, NOT persisted).

For each in-scope project it reads the ``project_metrics`` trajectory, detects the
biggest recent adverse inflection (``inflection.detect_inflection`` — pure), and
ranks the detections across projects by severity x magnitude x recency. Fast and
always-on: no model call, no persistence. Scope narrows to the caller's projects
(a comma-separated project_key list); absent -> all projects (bounded).
"""
from __future__ import annotations

from datetime import datetime, timezone

from risk_analytics_api.common.utilities import utc_now
from risk_analytics_api.daos.connection import MongoDatabaseFactory
from risk_analytics_api.dtos.responses import EarlyWarning, EarlyWarningsResponse
from risk_analytics_api.interfaces.services import EarlyWarningService
from risk_analytics_api.services.early_warning.inflection import (
    Inflection,
    confidence_for,
    detect_inflection,
)

#: Upper bound on projects scanned per read (keeps the always-on feed cheap).
_MAX_PROJECTS = 200
#: Trajectory snapshots read per project (newest window).
_TRAJECTORY_WINDOW = 12


def _to_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return utc_now()
    return utc_now()


def _epoch(value: object) -> float:
    dt = _to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


class DefaultEarlyWarningService(EarlyWarningService):
    def __init__(self, mongo: MongoDatabaseFactory) -> None:
        self._mongo = mongo

    def _in_scope_projects(self, scope: str | None) -> list[str]:
        if scope:
            keys = [p.strip() for p in scope.split(",") if p.strip()]
            if keys:
                return keys[:_MAX_PROJECTS]
        db = self._mongo.db()
        keys = [k for k in db["project_metrics"].distinct("project_key") if k]
        keys.sort()
        return keys[:_MAX_PROJECTS]

    def _history(self, project_key: str) -> list[dict]:
        cursor = (
            self._mongo.db()["project_metrics"]
            .find({"project_key": project_key}, {"_id": 0})
            .sort("computed_at", -1)
            .limit(_TRAJECTORY_WINDOW)
        )
        return list(cursor)

    def warnings(self, scope: str | None, limit: int) -> EarlyWarningsResponse:
        detections: list[tuple[Inflection, int]] = []
        for key in self._in_scope_projects(scope):
            history = self._history(key)
            inf = detect_inflection(key, history)
            if inf is not None:
                detections.append((inf, len(history)))

        if not detections:
            return EarlyWarningsResponse(items=[])

        epochs = [_epoch(inf.to_computed_at) for inf, _ in detections]
        newest, oldest = max(epochs), min(epochs)
        span = (newest - oldest) or 1.0

        scored: list[tuple[float, EarlyWarning]] = []
        for inf, points in detections:
            recency = 0.5 + 0.5 * ((_epoch(inf.to_computed_at) - oldest) / span)
            rank_score = inf.severity_rank * inf.magnitude * recency
            scored.append((rank_score, EarlyWarning(
                project_key=inf.project_key, metric=inf.metric,
                from_value=inf.from_value, to_value=inf.to_value,
                window=self._window_label(inf), direction=inf.direction,
                severity=inf.severity, cause=inf.cause,
                confidence=confidence_for(inf, points),
                detected_at=_to_datetime(inf.to_computed_at),
            )))

        scored.sort(key=lambda s: s[0], reverse=True)
        capped = max(1, min(int(limit), 100))
        return EarlyWarningsResponse(items=[w for _, w in scored[:capped]])

    @staticmethod
    def _window_label(inf: Inflection) -> str:
        frm = _to_datetime(inf.from_computed_at).date().isoformat()
        to = _to_datetime(inf.to_computed_at).date().isoformat()
        return f"{frm} to {to}"
