"""Contract tests for the HTTP surface with fake DAOs (no Postgres needed)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from admin_api.api.dependencies import (
    provide_get_audit_history_facade,
    provide_get_system_health_facade,
    provide_manage_agents_facade,
)
from admin_api.api.main import create_app
from admin_api.common.configuration import Settings
from admin_api.dtos.responses import AgentConfigResponse, AuditEventResponse, SystemHealthResponse
from admin_api.facades.get_audit_history import GetAuditHistoryFacade
from admin_api.facades.get_system_health import GetSystemHealthFacade
from admin_api.facades.manage_agents import ManageAgentsFacade
from admin_api.interfaces.daos import AgentConfigDao, AuditDao
from admin_api.interfaces.facades import GetSystemHealthUseCase
from admin_api.services.agent_management import DefaultAgentManagementService
from admin_api.services.audit_management import DefaultAuditManagementService


class _FakeConfigDao(AgentConfigDao):
    def __init__(self):
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


class _FakeAuditDao(AuditDao):
    def __init__(self):
        self.events: list[AuditEventResponse] = []

    def append(self, event):
        self.events.append(event)
        return event

    def list(self, limit, offset):
        ordered = list(reversed(self.events))
        return ordered[offset : offset + limit], len(ordered)


class _FakeSystemHealth(GetSystemHealthUseCase):
    def __init__(self, config_dao):
        self._config = config_dao

    def execute(self):
        total, enabled = self._config.counts()
        return SystemHealthResponse(
            status="ok", service="admin-api",
            dependencies={"postgresql": "ok"},
            agent_count=total, enabled_agent_count=enabled,
        )


def _client() -> TestClient:
    app = create_app()
    cfg, audit = _FakeConfigDao(), _FakeAuditDao()
    agents_service = DefaultAgentManagementService(cfg, audit)
    audit_service = DefaultAuditManagementService(audit)
    app.dependency_overrides[provide_manage_agents_facade] = lambda: ManageAgentsFacade(agents_service)
    app.dependency_overrides[provide_get_audit_history_facade] = (
        lambda: GetAuditHistoryFacade(audit_service)
    )
    app.dependency_overrides[provide_get_system_health_facade] = lambda: _FakeSystemHealth(cfg)
    return TestClient(app)


def test_liveness_ok() -> None:
    assert _client().get("/health/live").json()["status"] == "ok"


def test_upsert_then_get_agent_and_audit_and_health() -> None:
    client = _client()

    put = client.put(
        "/api/v1/admin/agents/schedule_risk",
        json={"model": "claude-opus-4-8", "framework": "crewai", "enabled": True},
    )
    assert put.status_code == 200
    assert put.json()["framework"] == "crewai"

    got = client.get("/api/v1/admin/agents/schedule_risk")
    assert got.status_code == 200 and got.json()["model"] == "claude-opus-4-8"

    listed = client.get("/api/v1/admin/agents")
    assert listed.json()["page"]["total"] == 1

    audit = client.get("/api/v1/admin/audit")
    assert audit.json()["page"]["total"] == 1
    assert audit.json()["items"][0]["action"] == "created"
    assert audit.json()["items"][0]["details"]["framework"] == "crewai"

    health = client.get("/api/v1/admin/system/health")
    assert health.json()["agent_count"] == 1 and health.json()["enabled_agent_count"] == 1


def test_get_missing_agent_returns_404() -> None:
    resp = _client().get("/api/v1/admin/agents/nope")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_invalid_framework_returns_422() -> None:
    resp = _client().put(
        "/api/v1/admin/agents/critic",
        json={"model": "claude-opus-4-8", "framework": "not-a-framework"},
    )
    assert resp.status_code == 422
