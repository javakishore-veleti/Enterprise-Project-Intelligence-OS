"""Use case: a ranked, scoped, time-aware attention feed for managers.

The facade turns the validated ``as_of`` date into an exclusive end-of-day upper
bound and supplies the reference ``now`` for recency scoring; the service does
the ranking + pagination.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from risk_analytics_api.dtos.responses import AttentionResponse
from risk_analytics_api.interfaces.facades import GetAttentionFeedUseCase
from risk_analytics_api.interfaces.services import AttentionService


class GetAttentionFeedFacade(GetAttentionFeedUseCase):
    def __init__(self, service: AttentionService) -> None:
        self._service = service

    def execute(
        self, top: int, as_of: date | None, projects: list[str] | None, offset: int
    ) -> AttentionResponse:
        as_of_str: str | None = None
        as_of_end: datetime | None = None
        if as_of is not None:
            as_of_str = as_of.isoformat()
            # Exclusive upper bound = midnight of the following day (UTC) so the
            # whole of ``as_of`` is included ("on or before the end of that day").
            as_of_end = datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=timezone.utc)

        return self._service.feed(
            top=top,
            offset=offset,
            as_of=as_of_str,
            as_of_end=as_of_end,
            projects=projects,
            now=datetime.now(timezone.utc),
        )
