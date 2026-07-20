"""Auth tests: pure key check + endpoint enforcement when enabled."""
from __future__ import annotations

from fastapi.testclient import TestClient

from ingestion_api.common.configuration import get_settings
from ingestion_api.common.security import verify_api_key


def test_verify_api_key() -> None:
    assert verify_api_key(None, "k", enabled=False) is True   # disabled -> allow
    assert verify_api_key("k", "k", enabled=True) is True
    assert verify_api_key("x", "k", enabled=True) is False
    assert verify_api_key(None, "k", enabled=True) is False
    assert verify_api_key("k", "", enabled=True) is False     # no key configured


def test_health_public_and_business_secured(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("API_KEY", "secret")
    get_settings.cache_clear()
    try:
        from ingestion_api.api.main import create_app
        client = TestClient(create_app())
        assert client.get("/health/live").status_code == 200          # public
        r = client.get("/api/v1/ingestion/datasets/public-jira")       # no key
        assert r.status_code == 401
        # a valid key passes the auth gate (may then fail on DB, but not 401)
        r2 = client.get("/api/v1/ingestion/datasets/public-jira",
                        headers={"X-API-Key": "secret"})
        assert r2.status_code != 401
    finally:
        get_settings.cache_clear()
