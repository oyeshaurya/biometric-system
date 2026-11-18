"""Fixtures: temp DB, fake-engine context, seeded admin, authenticated client."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def temp_env(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("BIOMETRIC_LAB_DB_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("BIOMETRIC_LAB_SESSION_SECRET", "test-secret-value-at-least-32-chars")
    monkeypatch.setenv("BIOMETRIC_LAB_ENGINE", "fake")

    from biometric_lab.config import get_settings
    from biometric_lab.db.init import create_schema
    from biometric_lab.db.session import get_engine, reset_engine_for_tests

    get_settings.cache_clear()
    reset_engine_for_tests()
    settings = get_settings()
    engine = get_engine(settings)
    create_schema(engine, with_triggers=False)
    yield settings
    reset_engine_for_tests()
    get_settings.cache_clear()


@pytest.fixture
def context(temp_env):
    from biometric_lab.context import build_test_context

    return build_test_context(settings=temp_env)


@pytest.fixture
def admin(temp_env):
    from biometric_lab.db.session import session_scope
    from biometric_lab.services.audit import AuditService
    from biometric_lab.services.auth import AuthService
    from biometric_lab.services.settings import SettingsService

    with session_scope() as session:
        SettingsService(session, AuditService(session)).seed_defaults(temp_env)
        AuthService(session, AuditService(session)).create_operator(
            "admin", "password123", role="admin"
        )
    return {"username": "admin", "password": "password123"}


@pytest.fixture
def operator(temp_env, admin):
    from biometric_lab.db.session import session_scope
    from biometric_lab.services.audit import AuditService
    from biometric_lab.services.auth import AuthService

    with session_scope() as session:
        AuthService(session, AuditService(session)).create_operator(
            "oper", "password123", role="operator"
        )
    return {"username": "oper", "password": "password123"}


@pytest.fixture
def client(temp_env, context):
    from biometric_lab.main import create_app

    app = create_app(context=context, settings=temp_env)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client, admin):
    resp = client.post("/api/auth/login", json=admin)
    assert resp.status_code == 200, resp.text
    client.headers.update({"X-CSRF-Token": resp.json()["csrf_token"]})
    return client
