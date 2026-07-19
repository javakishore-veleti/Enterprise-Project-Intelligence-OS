"""Executive Reporting reporter (LLM) — a leadership-level summary (RiskReport)."""
from __future__ import annotations

from datetime import datetime, timezone

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from agent_core import ReportKind, Reporter, ReviewContext, RiskReport
from executive_reporting.prompts import SYSTEM_PROMPT, build_user_prompt

AGENT_KEY = "executive_reporting"
DEFAULT_MODEL = "claude-opus-4-8"


class _Section(BaseModel):
    heading: str
    body: str


class _ReportOut(BaseModel):
    title: str
    summary: str
    sections: list[_Section] = Field(default_factory=list)


class ExecutiveReportingReporter(Reporter):
    agent_key = AGENT_KEY

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._llm = ChatAnthropic(model=model, max_tokens=1500, timeout=90).with_structured_output(
            _ReportOut
        )

    def report(self, context: ReviewContext) -> RiskReport:
        out: _ReportOut = self._llm.invoke(
            [("system", SYSTEM_PROMPT), ("human", build_user_prompt(context))]
        )
        return RiskReport(
            kind=ReportKind.EXECUTIVE,
            title=out.title,
            summary=out.summary,
            sections=[{"heading": s.heading, "body": s.body} for s in out.sections],
            source_agent=AGENT_KEY,
            generated_at=datetime.now(timezone.utc),
        )


def build(model: str = DEFAULT_MODEL, framework: str = "langgraph") -> ExecutiveReportingReporter:
    return ExecutiveReportingReporter(model=model)
