"""Unit tests for the analysis orchestrator with fakes (no LLM, no DB).

Verifies the full wiring: evidence -> agent config -> framework toggle ->
agent -> persistence -> run assembly, using an in-memory agent that returns a
deterministic finding.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent_core import (
    EvidenceMetrics,
    EvidencePackage,
    RiskAgent,
    RiskCategory,
    RiskFinding,
    Severity,
)

from risk_analytics_api.common.configuration import Settings
from risk_analytics_api.common.exceptions import AgentExecutionError, NotFoundError
from risk_analytics_api.dtos.common import AnalysisStatus
from risk_analytics_api.dtos.requests import StartAnalysisRequest
from risk_analytics_api.dtos.responses import AnalysisRunResponse, RiskFindingResponse
from risk_analytics_api.interfaces.daos import (
    AgentConfigGateway,
    EvidenceDao,
    GraphRunDao,
    RiskFindingDao,
)
from risk_analytics_api.interfaces.services import EvidenceRetrievalService
from risk_analytics_api.services.analysis_orchestration import (
    DefaultAnalysisOrchestrationService,
)

EVIDENCE = EvidencePackage(
    project_key="APACHE", project_name="Apache", metrics=EvidenceMetrics(blocker_count=5)
)


class FakeEvidenceService(EvidenceRetrievalService):
    def __init__(self, package=EVIDENCE):
        self._package = package

    def for_project(self, project_key):
        if self._package is None:
            raise NotFoundError(project_key)
        return self._package


class FakeConfigGateway(AgentConfigGateway):
    def __init__(self, cfg=(True, "claude-opus-4-8", "langgraph")):
        self._cfg = cfg

    def get(self, agent_key):
        return self._cfg


class FakeAgent(RiskAgent):
    agent_key = "schedule_risk"
    category = RiskCategory.SCHEDULE

    def __init__(self, captured):
        self._captured = captured

    def analyze(self, evidence):
        self._captured["framework_evidence"] = evidence
        return [
            RiskFinding(
                risk_category=RiskCategory.SCHEDULE,
                probability=0.6, impact=0.7, severity=Severity.HIGH, score=42.0,
                confidence=0.8, explanation="deterministic test finding",
                assumptions=["a"], recommended_actions=["do x"], affected=["APACHE"],
                source_agent="schedule_risk",
                analysis_timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
            )
        ]


class InMemoryFindingDao(RiskFindingDao):
    def __init__(self):
        self.by_run: dict[str, list[RiskFindingResponse]] = {}

    def add_many(self, run_id, project_key, findings):
        rows = self.by_run.setdefault(run_id, [])
        ids = []
        for i, f in enumerate(findings):
            fid = f"{run_id}-{i}"
            ids.append(fid)
            rows.append(RiskFindingResponse(
                finding_id=fid, agent_key=f.source_agent, risk_category=f.risk_category.value,
                probability=f.probability, impact=f.impact, severity=f.severity.value,
                score=f.score, confidence=f.confidence, explanation=f.explanation,
                assumptions=f.assumptions, recommended_actions=f.recommended_actions,
                affected=f.affected, analysis_timestamp=f.analysis_timestamp,
            ))
        return ids

    def list_for_run(self, run_id):
        return self.by_run.get(run_id, [])


class InMemoryGraphRunDao(GraphRunDao):
    def __init__(self, findings: InMemoryFindingDao):
        self.rows: dict[str, dict] = {}
        self._findings = findings

    def create(self, run_id, project_key, agent_keys, started_at):
        self.rows[run_id] = {"project_key": project_key, "status": "RUNNING",
                             "agent_keys": agent_keys, "started_at": started_at, "finished_at": None}

    def complete(self, run_id, status, finished_at):
        self.rows[run_id]["status"] = status
        self.rows[run_id]["finished_at"] = finished_at

    def get(self, run_id):
        r = self.rows.get(run_id)
        if r is None:
            return None
        return AnalysisRunResponse(
            run_id=run_id, project_key=r["project_key"], status=AnalysisStatus(r["status"]),
            agent_keys=r["agent_keys"], started_at=r["started_at"], finished_at=r["finished_at"],
            findings=self._findings.list_for_run(run_id),
        )


def _service(agent_factory, evidence=EVIDENCE, cfg=(True, "claude-opus-4-8", "langgraph")):
    findings = InMemoryFindingDao()
    runs = InMemoryGraphRunDao(findings)
    return DefaultAnalysisOrchestrationService(
        evidence_service=FakeEvidenceService(evidence),
        agent_config_gateway=FakeConfigGateway(cfg),
        graph_run_dao=runs,
        risk_finding_dao=findings,
        agent_factory=agent_factory,
        settings=Settings(),
    ), runs


def test_run_executes_agent_and_persists_findings() -> None:
    captured = {}
    service, runs = _service(lambda k, fw, m: FakeAgent(captured))

    result = service.run("APACHE", StartAnalysisRequest(agents=["schedule_risk"]))

    assert result.status is AnalysisStatus.COMPLETED
    assert result.finished_at is not None
    assert len(result.findings) == 1
    assert result.findings[0].severity == "high"
    assert result.findings[0].risk_category == "schedule"
    assert captured["framework_evidence"].project_key == "APACHE"


def test_missing_project_raises_before_creating_run() -> None:
    service, runs = _service(lambda k, fw, m: FakeAgent({}), evidence=None)
    with pytest.raises(NotFoundError):
        service.run("GHOST", StartAnalysisRequest())
    assert runs.rows == {}  # no dangling run created


def test_unimplemented_agent_is_skipped_completed_empty() -> None:
    service, _ = _service(lambda k, fw, m: None)  # factory returns None
    result = service.run("APACHE", StartAnalysisRequest(agents=["quality_risk"]))
    assert result.status is AnalysisStatus.COMPLETED
    assert result.findings == []


def test_agent_failure_marks_run_failed() -> None:
    class Boom(FakeAgent):
        def analyze(self, evidence):
            raise RuntimeError("model exploded")

    service, runs = _service(lambda k, fw, m: Boom({}))
    with pytest.raises(AgentExecutionError):
        service.run("APACHE", StartAnalysisRequest(agents=["schedule_risk"]))
    (run,) = runs.rows.values()
    assert run["status"] == "FAILED"


def test_get_run_missing_raises() -> None:
    service, _ = _service(lambda k, fw, m: FakeAgent({}))
    with pytest.raises(NotFoundError):
        service.get_run("nope")
