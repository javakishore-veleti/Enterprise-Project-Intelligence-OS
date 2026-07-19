"""Project Reporting reporter (LLM) — a project-level risk report (RiskReport)."""
from __future__ import annotations

from datetime import datetime, timezone

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from agent_core import ReportKind, Reporter, ReviewContext, RiskReport
from project_reporting.prompts import SYSTEM_PROMPT, build_user_prompt

AGENT_KEY = "project_reporting"
DEFAULT_MODEL = "claude-opus-4-8"


class _Section(BaseModel):
    heading: str
    body: str


class _ReportOut(BaseModel):
    title: str
    summary: str
    sections: list[_Section] = Field(default_factory=list)


class ProjectReportingReporter(Reporter):
    agent_key = AGENT_KEY

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._llm = ChatAnthropic(model=model, max_tokens=2000, timeout=90).with_structured_output(
            _ReportOut
        )

    def report(self, context: ReviewContext) -> RiskReport:
        out: _ReportOut = self._llm.invoke(
            [("system", SYSTEM_PROMPT), ("human", build_user_prompt(context))]
        )
        return RiskReport(
            kind=ReportKind.PROJECT,
            title=out.title,
            summary=out.summary,
            sections=[{"heading": s.heading, "body": s.body} for s in out.sections],
            source_agent=AGENT_KEY,
            generated_at=datetime.now(timezone.utc),
        )


def build(model: str = DEFAULT_MODEL, framework: str = "langgraph") -> ProjectReportingReporter:
    return ProjectReportingReporter(model=model)
