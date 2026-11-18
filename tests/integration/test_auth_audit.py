"""Auth, roles, CSRF and audit-chain tamper detection."""

from __future__ import annotations

from tests.integration.helpers import SHA256_HEX


def test_unauthenticated_blocked(client):
    assert client.get("/api/participants").status_code == 401


def test_operator_cannot_access_admin(client, operator):
    resp = client.post("/api/auth/login", json=operator)
    client.headers.update({"X-CSRF-Token": resp.json()["csrf_token"]})
    assert client.get("/api/settings").status_code == 403


def test_missing_csrf_rejected(client, admin):
    client.post("/api/auth/login", json=admin)  # cookie set, but no CSRF header
    resp = client.post("/api/participants", json={"subject_code": "X1"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "CSRF_MISSING"


def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


def test_setting_change_is_audited_and_threshold_validated(auth_client):
    ok = auth_client.put("/api/settings/operating_threshold", json={"value": 0.5, "reason": "dev EER"})
    assert ok.status_code == 200
    assert ok.json()["new"] == 0.5
    bad = auth_client.put(
        "/api/settings/operating_threshold", json={"value": 5.0, "reason": "too high"}
    )
    assert bad.status_code == 400


def test_audit_chain_detects_tampering(auth_client, temp_env):
    # create some audit events
    auth_client.post("/api/participants", json={"subject_code": "T1"})
    # tamper directly (schema created without triggers in tests)
    from sqlalchemy import update

    from biometric_lab.db.models import AuditEvent
    from biometric_lab.db.session import session_scope

    with session_scope() as session:
        first = session.query(AuditEvent).order_by(AuditEvent.id).first()
        session.execute(
            update(AuditEvent).where(AuditEvent.id == first.id).values(summary_json={"tampered": True})
        )

    verify = auth_client.get("/api/audit/verify").json()
    assert verify["valid"] is False
    assert verify["first_broken_id"] is not None


def test_retention_dry_run(auth_client):
    resp = auth_client.post("/api/admin/retention/run?dry_run=true")
    assert resp.status_code == 200
    assert resp.json()["dry_run"] is True
