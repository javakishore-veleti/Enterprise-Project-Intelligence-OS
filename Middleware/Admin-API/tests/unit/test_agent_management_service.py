"""Unit tests for agent management against in-memory fake DAOs."""
from __future__ import annotations

import pytest

from admin_api.common.exceptions import NotFoundError
from admin_api.dtos.common import AgentFramework
from admin_api.dtos.requests import UpsertAgentConfigRequest
from admin_api.dtos.responses import AgentConfigResponse, AuditEventResponse
from admin_api.interfaces.daos import AgentConfigDao, AuditDao
from admin_api.services.agent_management import DefaultAgentManagementService


class FakeConfigDao(AgentConfigDao):
    def __init__(self) -> None:
        self.rows: dict[str, AgentConfigResponse] = {}

    def list(self, limit, offset):
        ordered = [self.rows[k] for k in sorted(self.rows)]
        return ordered[offset : offset + limit], len(ordered)

    def get(self, agent_key):
        return self.rows.get(agent_key)

    def upsert(self, config):
        self.rows[config.agent_key] = config
        return config

    def counts(self):
        return len(self.rows), sum(1 for c in self.rows.values() if c.enabled)


class FakeAuditDao(AuditDao):
    def __init__(self) -> None:
        self.events: list[AuditEventResponse] = []

    def append(self, event):
        self.events.append(event)
        return event

    def list(self, limit, offset):
        ordered = list(reversed(self.events))
        return ordered[offset : offset + limit], len(ordered)


def _service():
    cfg, audit = FakeConfigDao(), FakeAuditDao()
    return DefaultAgentManagementService(cfg, audit), cfg, audit


def test_create_writes_config_and_audit_event() -> None:
    service, cfg, audit = _service()

    saved = service.upsert(
        "schedule_risk",
        UpsertAgentConfigRequest(model="claude-opus-4-8", framework=AgentFramework.LANGGRAPH),
    )

    assert saved.agent_key == "schedule_risk"
    assert saved.display_name == "Schedule Risk"
    assert "schedule_risk" in cfg.rows
    assert len(audit.events) == 1
    assert audit.events[0].action == "created"
    assert audit.events[0].details["framework"] == "langgraph"


def test_update_toggles_framework_and_audits_update() -> None:
    service, _, audit = _service()
    service.upsert("critic", UpsertAgentConfigRequest(model="claude-opus-4-8"))

    updated = service.upsert(
        "critic",
        UpsertAgentConfigRequest(model="claude-sonnet-5", framework=AgentFramework.CREWAI),
    )

    assert updated.framework is AgentFramework.CREWAI
    assert updated.model == "claude-sonnet-5"
    assert [e.action for e in audit.events] == ["created", "updated"]
    assert audit.events[-1].details["framework"] == "crewai"


def test_get_missing_raises_not_found() -> None:
    service, _, _ = _service()
    with pytest.raises(NotFoundError):
        service.get("nope")


def test_list_paginates() -> None:
    service, _, _ = _service()
    for key in ("a", "b", "c"):
        service.upsert(key, UpsertAgentConfigRequest(model="claude-opus-4-8"))
    result = service.list(limit=2, offset=0)
    assert result.page.total == 3 and len(result.items) == 2
