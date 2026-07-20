"""Auth: pure check + enforcement when enabled."""
from __future__ import annotations

from fastapi.testclient import TestClient

from risk_analytics_api.common.configuration import get_settings
from risk_analytics_api.common.security import verify_api_key


def test_verify_api_key() -> None:
    assert verify_api_key(None, "k", enabled=False) is True
    assert verify_api_key("k", "k", enabled=True) is True
    assert verify_api_key("x", "k", enabled=True) is False


def test_health_public_business_secured(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEY", "secret")
    get_settings.cache_clear()
    try:
        from risk_analytics_api.api.main import create_app
        c = TestClient(create_app())
        assert c.get("/health/live").status_code == 200
        assert c.get("/api/v1/analysis/runs/none").status_code == 401
        assert c.get("/api/v1/analysis/runs/none",
                     headers={"X-API-Key": "secret"}).status_code != 401
    finally:
        get_settings.cache_clear()
