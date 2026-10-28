"""Auth middleware doğrulaması: API_KEY boşsa AUTH YOK, doluysa X-API-Key header zorunlu."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)

# Public endpointler: kök (/) ve scheduler/status (kendinden önce API_KEY boş iken auth kapalı (varsayılan dev/test).

_PUBLIC_GET = ["/", "/api/v1/scheduler/status", "/api/v1/matching/health"]
_HASSAS_GET = [
    "/api/v1/profile?user_id=x",
    "/api/v1/jobs?user_id=x",
    "/api/v1/watchers",
    "/api/v1/archive/jobs?user_id=x",
    "/api/v1/notifications?user_id=x",
    "/api/v1/notifications/unread-count?user_id=x",
    "/api/v1/logs?user_id=x",
]
_HASSAS_WRITE = [
    ("POST", "/api/v1/scheduler/run", {}),
    ("POST", "/api/v1/scheduler/stop", {}),
]


def _set_api_key(monkeypatch, value: str) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("API_KEY", value)
    # Yeni settings yüklenmesi için
    get_settings()


def test_public_endpoints_auth_disabled_when_api_key_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_api_key(monkeypatch, "")
    for path in _PUBLIC_GET:
        resp = client.get(path)
        assert resp.status_code < 500, f"{path} {resp.status_code}"


def test_hassas_endpoints_pass_without_key_when_api_key_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """API_KEY boşsa auth kapalı, 401 DÖNMEMELİ (backward uyum — eski 49 test için önemli."""
    _set_api_key(monkeypatch, "")
    for path in _HASSAS_GET:
        resp = client.get(path)
        assert resp.status_code != 401, f"{path} boş API_KEY iken 401 dönmemeli"
    for method, path, _ in _HASSAS_WRITE:
        # 401 OLMAYACAK (dönen kod 404, 422 vs. olabilir)
        fn = getattr(client, method.lower())
        resp = fn(path, json={})
        assert resp.status_code != 401, f"{method} {path} 401 dönmemeli (backward)"


def test_hassas_endpoints_require_key_when_configured(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_api_key(monkeypatch, "gizli-anahtar-123")
    for path in _HASSAS_GET:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} API_KEY var iken header olmadan 401 dönmeli"
    for method, path, _ in _HASSAS_WRITE:
        fn = getattr(client, method.lower())
        resp = fn(path, json={})
        assert resp.status_code == 401, f"{method} {path} 401 dönmeli (header yok)"


def test_wrong_key_returns_401(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_api_key(monkeypatch, "dogru-key")
    resp = client.get("/api/v1/watchers", headers={"X-API-Key": "yanlis-key"})
    assert resp.status_code == 401


def test_correct_key_passes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_api_key(monkeypatch, "dogru-key")
    # Herhangi bir 401 HARİÇ status — izin
    resp = client.get("/api/v1/watchers", headers={"X-API-Key": "dogru-key"})
    assert resp.status_code != 401
    # Public endpointler hala serbest
    assert client.get("/").status_code == 200


@pytest.fixture(autouse=True)
def _reset_api_key_after() -> None:
    yield
    get_settings.cache_clear()
    os.environ.pop("API_KEY", None)
    get_settings()
