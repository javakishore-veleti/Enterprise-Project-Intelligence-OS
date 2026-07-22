"""Forecast narration — a bounded LangGraph that interprets the deterministic facts.

The numbers (on-time probability, credible interval, slip range, drivers) are
computed upstream by ``services/forecast/forecasting`` — pure Python, no LLM. This
graph runs ONE structured-output LLM turn that *narrates* those facts and argues
both sides (bull / bear / what-would-change-my-mind). It reuses the
``delivery_forecasting`` agent's release-readiness persona (its ``SYSTEM_PROMPT``
and evidence prompt) so the interpretation is grounded in the same evidence the
detector reasons over.

Orchestration is a single-node ``StateGraph`` (``narrate -> END``) — trivially
bounded, and consistent with the delivery_forecasting adapter's own shape. The
chat model is injected so tests run a fake (no real model call).
"""
from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agent_core import EvidencePackage
from delivery_forecasting.prompts import SYSTEM_PROMPT, build_user_prompt

#: A forecast never loops; the single node makes the bound explicit.
DEFAULT_MAX_ITERATIONS = 1

_NARRATION_PROMPT = (
    "You are given a project's DETERMINISTIC delivery forecast, already computed "
    "from its metric-history trajectory. Do NOT recompute the numbers — interpret "
    "them.\n\n"
    "{facts}\n\n"
    "Explain what this forecast means for delivery in plain language, then argue "
    "both sides:\n"
    "- bull_case: the realistic path where the project still lands on time.\n"
    "- bear_case: the realistic path where it slips.\n"
    "- would_change_mind: the single observation that would most change this call.\n"
    "Set confidence (0-1) reflecting how much trajectory evidence supports the "
    "forecast (lower it when the trajectory is short or noisy). Ground every "
    "statement in the supplied facts and evidence; never invent issue keys or counts."
)


class _Narration(BaseModel):
    """Structured narration the model returns over the deterministic facts.

    Every field has a default so a partial tool-call from the model still
    validates instead of 500-ing the whole forecast; ``_narrate`` fills a
    deterministic fallback when the model omits the narrative entirely.
    """

    narrative: str = Field(default="", description="Plain-language reading of the forecast.")
    bull_case: str = Field(default="", description="The path to landing on time.")
    bear_case: str = Field(default="", description="The path to slipping.")
    would_change_mind: str = Field(
        default="", description="The single observation that would most change the call.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in the forecast (0-1).")


class _State(TypedDict, total=False):
    facts: str
    evidence: EvidencePackage
    narration: _Narration


def format_facts(facts: Any, evidence: EvidencePackage) -> str:
    """Render the deterministic forecast facts into a compact prompt block."""
    drivers = "\n".join(
        f"  - {d['factor']} ({d['direction']}): {d['detail']}" for d in facts.drivers
    ) or "  - (no dominant driver)"
    return (
        f"On-time probability: {facts.on_time_probability:.0%} "
        f"(credible interval {facts.probability_low:.0%}-{facts.probability_high:.0%})\n"
        f"Projected slip: {facts.projected_slip_days_low}-{facts.projected_slip_days_high} days\n"
        f"Outlook: {facts.outlook}\n"
        f"Trajectory snapshots analyzed: {facts.trajectory_points}\n"
        f"Drivers:\n{drivers}\n\n"
        f"Underlying evidence:\n{build_user_prompt(evidence)}"
    )


class ForecastNarrator:
    """A bounded single-turn LangGraph that narrates a deterministic forecast."""

    def __init__(self, chat_model: Any) -> None:
        self._llm = chat_model.with_structured_output(_Narration)
        self._graph = self._build()

    def _build(self):
        graph = StateGraph(_State)
        graph.add_node("narrate", self._narrate)
        graph.add_edge(START, "narrate")
        graph.add_edge("narrate", END)
        return graph.compile()

    def _narrate(self, state: _State) -> _State:
        # A genuine model/API failure propagates (the service persists FAILED and
        # re-raises). The field defaults on _Narration mean a partial tool-call
        # validates rather than 500-ing; if it still comes back empty, fall back
        # deterministically so the computed forecast is never lost.
        prompt = _NARRATION_PROMPT.format(facts=state["facts"])
        narration: _Narration = self._llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        if not (narration.narrative or "").strip():
            narration = _Narration(
                narrative=(
                    "Forecast derived from the project's metric-history trajectory. "
                    "Automated narration was unavailable, so the computed probability, "
                    "credible interval, and drivers above are the forecast."
                ),
                confidence=narration.confidence,
            )
        return {"narration": narration}

    def run(self, facts: Any, evidence: EvidencePackage) -> _Narration:
        out = self._graph.invoke({"facts": format_facts(facts, evidence), "evidence": evidence})
        return out["narration"]
