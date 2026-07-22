"""Scenario narration — a bounded LangGraph that interprets the what-if trade-off.

The re-forecast (base vs projected probability, slip, portfolio risk) and the
cascade targets are computed upstream by ``services/scenario/cascade`` — pure
Python + bounded evidence reads, no LLM. This graph runs ONE structured-output
LLM turn that narrates the trade-off the scenario represents, grounded in those
deterministic facts. It reuses the ``delivery_forecasting`` release-readiness
persona for consistency with the forecast narrator.

Single-node ``StateGraph`` (``narrate -> END``) — trivially bounded. The chat
model is injected so tests run a fake (no real model call).
"""
from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from delivery_forecasting.prompts import SYSTEM_PROMPT

DEFAULT_MAX_ITERATIONS = 1

_NARRATION_PROMPT = (
    "A delivery what-if scenario has been simulated for a project. The numbers "
    "below are DETERMINISTIC — do NOT recompute them, interpret them.\n\n"
    "Scenario: {scenario}\n\n"
    "{facts}\n\n"
    "Narrate the trade-off this scenario represents: what it does to THIS project's "
    "delivery odds, and how the impact propagates to the coupled projects listed "
    "above (dependency and shared-contributor cascades). Be balanced — name both "
    "the upside and the cost. Ground every statement in the supplied facts; never "
    "invent projects, issue keys, or counts. Set confidence (0-1) reflecting how "
    "strong the coupling evidence is."
)


class _Narration(BaseModel):
    # Defaults so a partial model tool-call validates instead of 500-ing.
    narrative: str = Field(default="", description="Plain-language reading of the scenario trade-off.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in the simulation (0-1).")


class _State(TypedDict, total=False):
    scenario: str
    facts: str
    narration: _Narration


def format_facts(
    base_p: float, projected_p: float, base_slip: int, projected_slip: int,
    portfolio_risk_delta: float, cascades: list[dict],
) -> str:
    """Render the deterministic scenario facts into a compact prompt block."""
    lines = "\n".join(
        f"  - {c['project_key']} [{c['magnitude']}] {c['effect']}: {c['reason']}"
        for c in cascades
    ) or "  - (no coupled projects detected)"
    return (
        f"On-time probability: {base_p:.0%} -> {projected_p:.0%} "
        f"(delta {projected_p - base_p:+.0%})\n"
        f"Projected slip: {base_slip} -> {projected_slip} days\n"
        f"Portfolio risk delta: {portfolio_risk_delta:+.2f} "
        f"(positive = portfolio risk increased)\n"
        f"Cascade targets:\n{lines}"
    )


class ScenarioNarrator:
    """A bounded single-turn LangGraph that narrates a scenario trade-off."""

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
        # Genuine model/API failure propagates (service persists FAILED + re-raises);
        # defaults let a partial tool-call validate, and an empty narrative falls back.
        prompt = _NARRATION_PROMPT.format(scenario=state["scenario"], facts=state["facts"])
        narration: _Narration = self._llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        if not (narration.narrative or "").strip():
            narration = _Narration(
                narrative=(
                    "Scenario simulated from the project's trajectory and its coupled "
                    "projects. Automated narration was unavailable, so the computed "
                    "probability shift, slip change, and cascade targets above are the result."
                ),
                confidence=narration.confidence,
            )
        return {"narration": narration}

    def run(self, scenario: str, facts: str) -> _Narration:
        out = self._graph.invoke({"scenario": scenario, "facts": facts})
        return out["narration"]
