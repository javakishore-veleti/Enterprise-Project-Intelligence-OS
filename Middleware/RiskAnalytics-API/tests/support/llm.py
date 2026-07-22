"""A fake chat model that scripts a tool-call sequence + a canned conclusion.

Mirrors the ``ChatAnthropic`` surface the Investigation Agent uses:
``.bind_tools(tools)`` -> runnable returning scripted ``AIMessage``s (with
``tool_calls``); ``.with_structured_output(model)`` -> runnable returning the
canned conclusion. No real model is ever called.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from langchain_core.messages import AIMessage


def tool_call_msg(text: str, calls: list[tuple[str, dict, str]]) -> AIMessage:
    """Build an AIMessage that requests tools. ``calls`` = [(name, args, id), ...]."""
    return AIMessage(
        content=text,
        tool_calls=[{"name": n, "args": a, "id": i} for n, a, i in calls],
    )


def conclusion(**kwargs: Any) -> SimpleNamespace:
    base = dict(hypotheses=[], root_cause="", causal_chain=[], confidence=0.0,
                recommended_action="")
    base.update(kwargs)
    return SimpleNamespace(**base)


class _ToolRunnable:
    def __init__(self, script: list[AIMessage]) -> None:
        self._script = list(script)
        self._i = 0

    def invoke(self, messages: Any) -> AIMessage:
        if self._i < len(self._script):
            msg = self._script[self._i]
            self._i += 1
            return msg
        return AIMessage(content="done", tool_calls=[])


class _StructRunnable:
    def __init__(self, result: Any) -> None:
        self._result = result

    def invoke(self, messages: Any) -> Any:
        return self._result


class FakeChatModel:
    """Scripts the reasoning turns + the final structured conclusion."""

    def __init__(self, script: list[AIMessage], conclusion_result: Any) -> None:
        self._script = script
        self._conclusion = conclusion_result

    def bind_tools(self, tools: Any) -> _ToolRunnable:
        return _ToolRunnable(self._script)

    def with_structured_output(self, model: Any) -> _StructRunnable:
        return _StructRunnable(self._conclusion)
