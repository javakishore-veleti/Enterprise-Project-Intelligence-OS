"""Investigation Agent — a LangGraph ReAct-style tool-calling loop.

The agent is cast (by ``SYSTEM_PROMPT``) as a delivery-risk investigator. Given a
project (and an optional free-text question) it FORMS hypotheses, CALLS the
bounded evidence-store tools to gather facts, REASONS over the observations, and
CONCLUDES with a root cause + causal chain + confidence.

Orchestration is a LangGraph ``StateGraph``:

    reason --(tool calls?)--> act --> reason ... --> finalize

* ``reason`` — one LLM turn (tools bound); it either calls tools or stops.
* ``act`` — executes the requested tools, records each (action, observation,
  hypothesis) step + an evidence citation, and loops back.
* ``finalize`` — one structured-output LLM call that returns the conclusion.

The loop is **bounded**: ``act`` increments a counter and the router falls
through to ``finalize`` once ``max_iterations`` tool rounds have run, so the agent
always terminates. The LLM is injected (constructor arg), so tests pass a fake
that returns a canned tool-call sequence + conclusion — no real model call.
"""
from __future__ import annotations

import json
import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

DEFAULT_MAX_ITERATIONS = 8
#: Cap on the serialized observation stored per step (keeps the trace bounded).
_OBSERVATION_CHARS = 600

SYSTEM_PROMPT = (
    "You are an autonomous delivery-risk Investigation Agent for an enterprise "
    "project-intelligence platform. You are given ONE project to investigate.\n\n"
    "Method:\n"
    "1. Form 2-4 concrete hypotheses for why the project may be at risk "
    "(reopen churn, blocker pile-up, aging backlog, stalled dependencies, "
    "bus-factor / contributor concentration, slowing velocity).\n"
    "2. Test them by CALLING the evidence tools. Start with metrics_snapshot to "
    "orient, then drill into whichever tools your hypotheses need. Call a tool at "
    "a time and read its result before deciding the next.\n"
    "3. Reason ONLY over data the tools returned. NEVER invent issue keys, counts, "
    "names, or facts the tools did not report.\n"
    "4. When the evidence is sufficient, stop calling tools and give your "
    "conclusion: the single most likely root cause, the causal chain that leads "
    "to it, your confidence, and the single next action.\n"
    "Keep tool usage focused — a handful of calls, not exhaustive."
)


class _Conclusion(BaseModel):
    """Structured final answer the model returns after gathering evidence."""

    hypotheses: list[str] = Field(default_factory=list,
                                  description="The hypotheses considered during the investigation.")
    root_cause: str = Field(description="The single most likely root cause, grounded in tool evidence.")
    causal_chain: list[str] = Field(
        default_factory=list,
        description="Ordered links from underlying cause to delivery impact.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the root cause (0-1).")
    recommended_action: str = Field(description="The single highest-leverage next action.")


@dataclass
class InvestigationResult:
    """Framework-free result the service maps onto the response DTO."""

    hypotheses: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)          # {action, observation, hypothesis}
    evidence: list[dict] = field(default_factory=list)       # {kind, detail, count}
    root_cause: str = ""
    causal_chain: list[str] = field(default_factory=list)
    confidence: float = 0.0
    recommended_action: str = ""


class _State(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    steps: Annotated[list, operator.add]
    evidence: Annotated[list, operator.add]
    iters: Annotated[int, operator.add]
    conclusion: _Conclusion


def _text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(p for p in parts if p).strip()
    return ""


def _citation(name: str, result: dict) -> dict:
    """Build a grounded evidence citation from a tool's bounded result."""
    if name == "metrics_snapshot":
        metrics = result.get("metrics", {})
        pairs = ", ".join(f"{k}={v}" for k, v in metrics.items() if v not in (None, 0, 0.0))
        return {"kind": name, "detail": f"computed metrics: {pairs or 'all nominal'}", "count": None}
    if name == "contributor_breakdown":
        top = result.get("top") or []
        lead = top[0]["author"] if top else "n/a"
        return {"kind": name,
                "detail": (f"top contributor {lead} holds "
                           f"{result.get('concentration', 0.0):.0%} of {result.get('total_changes', 0)} changes"),
                "count": result.get("contributors")}
    count = result.get("count")
    return {"kind": name, "detail": f"{count} record(s) matched", "count": count}


class InvestigationAgent:
    """A bounded, tool-using LangGraph agent that root-causes delivery risk."""

    def __init__(
        self,
        chat_model: Any,
        tools: list[StructuredTool],
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._tools = {t.name: t for t in tools}
        self._llm_tools = chat_model.bind_tools(tools)
        self._llm_struct = chat_model.with_structured_output(_Conclusion)
        self._max = max(1, max_iterations)
        self._graph = self._build()

    def _build(self):
        graph = StateGraph(_State)
        graph.add_node("reason", self._reason)
        graph.add_node("act", self._act)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "reason")
        graph.add_conditional_edges("reason", self._route, {"act": "act", "finalize": "finalize"})
        graph.add_edge("act", "reason")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _reason(self, state: _State) -> _State:
        response = self._llm_tools.invoke(state["messages"])
        return {"messages": [response]}

    def _route(self, state: _State) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None) and state.get("iters", 0) < self._max:
            return "act"
        return "finalize"

    def _act(self, state: _State) -> _State:
        last = state["messages"][-1]
        hypothesis = _text(last)
        tool_messages: list = []
        steps: list = []
        evidence: list = []
        for call in last.tool_calls:
            name = call["name"]
            args = call.get("args", {}) or {}
            tool = self._tools.get(name)
            if tool is None:
                result = {"error": f"unknown tool '{name}'"}
            else:
                result = tool.invoke(args)
            observation = json.dumps(result, default=str)[:_OBSERVATION_CHARS]
            tool_messages.append(ToolMessage(content=observation, tool_call_id=call["id"]))
            arg_str = ", ".join(f"{k}={v}" for k, v in args.items())
            steps.append({
                "action": f"{name}({arg_str})",
                "observation": observation,
                "hypothesis": hypothesis or f"testing evidence via {name}",
            })
            if isinstance(result, dict) and "error" not in result:
                evidence.append(_citation(name, result))
        return {"messages": tool_messages, "steps": steps, "evidence": evidence, "iters": 1}

    def _finalize(self, state: _State) -> _State:
        prompt = HumanMessage(content=(
            "Based only on the tool evidence above, give your structured conclusion: "
            "the hypotheses you considered, the single root cause, the causal chain, "
            "your confidence (0-1), and the one recommended next action."
        ))
        conclusion: _Conclusion = self._llm_struct.invoke(state["messages"] + [prompt])
        return {"conclusion": conclusion}

    def run(
        self, project_key: str, question: str | None = None, emphasis: str | None = None
    ) -> InvestigationResult:
        user = f"Investigate project '{project_key}'."
        if question:
            user += f" Focus on this question: {question}"
        system = SYSTEM_PROMPT
        if emphasis:
            # Light-touch template bias (not a hard tool restriction).
            system += f"\n\nEmphasize these angles for this investigation: {emphasis}."
        initial = {
            "messages": [SystemMessage(content=system), HumanMessage(content=user)],
            "steps": [], "evidence": [], "iters": 0,
        }
        out = self._graph.invoke(initial, {"recursion_limit": 2 * self._max + 5})
        conclusion: _Conclusion = out["conclusion"]
        return InvestigationResult(
            hypotheses=list(conclusion.hypotheses),
            steps=out.get("steps", []),
            evidence=out.get("evidence", []),
            root_cause=conclusion.root_cause,
            causal_chain=list(conclusion.causal_chain),
            confidence=float(conclusion.confidence),
            recommended_action=conclusion.recommended_action,
        )
