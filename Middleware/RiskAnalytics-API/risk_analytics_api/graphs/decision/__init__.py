"""Decision options narration — a bounded LangGraph that leads with Options.

Decide is the prescriptive verb ("what should we do?"). The deterministic facts —
the delivery forecast (on-time probability, slip range, drivers), the open
blockers, and the top contributors — are computed upstream by pure Python (no
LLM). This graph runs ONE structured-output LLM turn that proposes **2-3 decision
options**, each with a prioritized action list, suggested owners (drawn from the
project's top contributors), a predicted outcome, trade-offs, a recovery estimate,
and a per-option confidence, plus a top-level narrative + confidence.

It reuses the ``mitigation_planning`` agent's persona (its ``SYSTEM_PROMPT``) so the
options are grounded, actionable, and never invent risks outside the evidence.

Orchestration is a single-node ``StateGraph`` (``propose -> END``) — trivially
bounded, consistent with the forecast/scenario narrators. The chat model is
injected so tests run a fake (no real model call). Structured-output fields all
default so a partial tool-call still validates; an empty result falls back to a
deterministic option so the decision is never lost.
"""
from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agent_core import EvidencePackage
from mitigation_planning.prompts import SYSTEM_PROMPT

#: A decision never loops; the single node makes the bound explicit.
DEFAULT_MAX_ITERATIONS = 1

#: Requested number of options; the model may return 2-3, we clamp to this range.
MIN_OPTIONS = 2
MAX_OPTIONS = 3

_PROPOSE_PROMPT = (
    "You are advising on a delivery decision: WHAT SHOULD WE DO about this "
    "project? Lead with OPTIONS. Given the project's DETERMINISTIC facts below "
    "(already computed — do NOT recompute them), propose {min}-{max} distinct, "
    "realistic decision options.\n\n"
    "{facts}\n\n"
    "For EACH option provide:\n"
    "- title: a short label for the course of action.\n"
    "- summary: 1-2 sentences on what this option is and when to pick it.\n"
    "- actions: a PRIORITIZED list of concrete steps (most important first).\n"
    "- suggested_owners: who should own the actions — draw ONLY from the "
    "candidate owners listed in the facts (the project's top contributors); do "
    "not invent names.\n"
    "- predicted_outcome: the likely delivery effect if this option is taken.\n"
    "- tradeoffs: what this option costs or risks versus the others.\n"
    "- recovery_estimate: a rough time-to-recover / time-to-effect (e.g. "
    "'2-4 weeks').\n"
    "- confidence: 0-1, how confident you are this option helps.\n\n"
    "Then set a top-level narrative comparing the options and a recommendation, "
    "and a top-level confidence (0-1) reflecting how much the evidence supports "
    "the call (lower it when the trajectory is short or the evidence is thin). "
    "Ground every statement in the supplied facts; never invent issue keys, "
    "counts, or contributor names."
)


class _Option(BaseModel):
    """One decision option the model returns. Every field defaults so a partial
    tool-call still validates instead of failing the whole decision."""

    title: str = Field(default="", description="Short label for this course of action.")
    summary: str = Field(default="", description="What this option is and when to pick it.")
    actions: list[str] = Field(default_factory=list, description="Prioritized concrete steps.")
    suggested_owners: list[str] = Field(
        default_factory=list, description="Owners drawn from the project's top contributors.")
    predicted_outcome: str = Field(default="", description="Likely delivery effect.")
    tradeoffs: str = Field(default="", description="What this option costs vs the others.")
    recovery_estimate: str = Field(default="", description="Rough time-to-recover / effect.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence (0-1).")


class _DecisionOptions(BaseModel):
    """Structured decision the model returns over the deterministic facts."""

    narrative: str = Field(default="", description="Comparison + recommendation across options.")
    options: list[_Option] = Field(default_factory=list, description="The 2-3 decision options.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Overall confidence (0-1).")


class _State(TypedDict, total=False):
    facts: str
    evidence: EvidencePackage
    decision: _DecisionOptions


def format_facts(facts: Any, evidence: EvidencePackage, top_contributors: list[str],
                 context: str | None) -> str:
    """Render the deterministic decision inputs into a compact prompt block."""
    drivers = "\n".join(
        f"  - {d['factor']} ({d['direction']}): {d['detail']}" for d in facts.drivers
    ) or "  - (no dominant driver)"
    observations = "\n".join(f"  - {o}" for o in evidence.observations) or "  - (none)"
    owners = ", ".join(top_contributors) if top_contributors else "(no contributor history)"
    m = evidence.metrics
    ctx = f"\nRequester context: {context}\n" if context else ""
    return (
        f"Project: {evidence.project_name} ({evidence.project_key})\n"
        f"On-time probability: {facts.on_time_probability:.0%} "
        f"(credible interval {facts.probability_low:.0%}-{facts.probability_high:.0%})\n"
        f"Projected slip: {facts.projected_slip_days_low}-{facts.projected_slip_days_high} days\n"
        f"Outlook: {facts.outlook}\n"
        f"Open blockers: {m.blocker_count}\n"
        f"Open issues: {m.open_issue_count} of {m.issue_count}\n"
        f"Trajectory snapshots analyzed: {facts.trajectory_points}\n"
        f"Candidate owners (top contributors, most active first): {owners}\n"
        f"Drivers:\n{drivers}\n"
        f"Observations:\n{observations}"
        f"{ctx}"
    )


class DecisionOptionsAgent:
    """A bounded single-turn LangGraph that proposes decision options."""

    def __init__(self, chat_model: Any) -> None:
        self._llm = chat_model.with_structured_output(_DecisionOptions)
        self._graph = self._build()

    def _build(self):
        graph = StateGraph(_State)
        graph.add_node("propose", self._propose)
        graph.add_edge(START, "propose")
        graph.add_edge("propose", END)
        return graph.compile()

    def _propose(self, state: _State) -> _State:
        # A genuine model/API failure propagates (the service persists FAILED and
        # re-raises). Field defaults on _Option/_DecisionOptions mean a partial
        # tool-call validates rather than failing; if it comes back with no
        # options, fall back deterministically so the decision is never lost.
        prompt = _PROPOSE_PROMPT.format(min=MIN_OPTIONS, max=MAX_OPTIONS, facts=state["facts"])
        decision: _DecisionOptions = self._llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        decision.options = [o for o in decision.options if (o.title or o.summary or o.actions)]
        if not decision.options:
            decision = self._fallback(state["evidence"])
        return {"decision": decision}

    def _fallback(self, evidence: EvidencePackage) -> _DecisionOptions:
        """Deterministic single option when the model returns nothing usable."""
        return _DecisionOptions(
            narrative=(
                "Automated option generation was unavailable, so this is a "
                "deterministic fallback derived from the computed evidence above. "
                "Review the drivers and blockers before acting."
            ),
            options=[_Option(
                title="Stabilize on current evidence",
                summary=(
                    "Act on the deterministic drivers and open blockers already "
                    "computed for this project."
                ),
                actions=[
                    "Triage the open blockers listed in the evidence.",
                    "Address the top driver moving the forecast.",
                    "Re-run the forecast after the next metrics snapshot.",
                ],
                suggested_owners=[],
                predicted_outcome="Stabilizes the trajectory while a fuller plan is formed.",
                tradeoffs="Reactive rather than strategic; buys time, not a decision.",
                recovery_estimate="1-2 weeks",
                confidence=0.3,
            )],
            confidence=0.3,
        )

    def run(self, facts: Any, evidence: EvidencePackage, top_contributors: list[str],
            context: str | None = None) -> _DecisionOptions:
        out = self._graph.invoke({
            "facts": format_facts(facts, evidence, top_contributors, context),
            "evidence": evidence,
        })
        return out["decision"]
