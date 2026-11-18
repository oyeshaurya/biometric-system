"""Settings, operators, retention and audit routes (FR-06, FR-16, FR-17, FR-18)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.api.deps import get_db, require_admin, verify_csrf
from biometric_lab.db.models import AuditEvent, Operator
from biometric_lab.schemas import OperatorCreate, SettingUpdate
from biometric_lab.services.audit import AuditService
from biometric_lab.services.auth import AuthService
from biometric_lab.services.retention import RetentionService
from biometric_lab.services.settings import SettingsService

router = APIRouter(tags=["admin"])


@router.get("/settings")
def get_settings_all(
    _op: Operator = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    return SettingsService(db, AuditService(db)).all()


@router.put("/settings/{key}")
def set_setting(
    key: str,
    body: SettingUpdate,
    op: Operator = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
) -> dict:
    result = SettingsService(db, AuditService(db)).set(
        key, body.value, reason=body.reason, actor_id=op.id
    )
    return result


@router.post("/admin/retention/run")
def run_retention(
    dry_run: bool = Query(default=True),
    op: Operator = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
) -> dict:
    audit = AuditService(db)
    service = RetentionService(db, SettingsService(db, audit), audit)
    return service.sweep(dry_run=dry_run, actor_id=op.id)


@router.get("/admin/operators")
def list_operators(
    _op: Operator = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    ops = AuthService(db, AuditService(db)).list_operators()
    return {
        "items": [
            {"id": o.id, "username": o.username, "role": o.role, "disabled": o.disabled}
            for o in ops
        ]
    }


@router.post("/admin/operators")
def create_operator(
    body: OperatorCreate,
    op: Operator = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
) -> dict:
    new_op = AuthService(db, AuditService(db)).create_operator(
        body.username, body.password, role=body.role, actor_id=op.id
    )
    return {"id": new_op.id, "username": new_op.username, "role": new_op.role}


@router.get("/audit")
def list_audit(
    action: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    cursor: int = Query(default=0),
    _op: Operator = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(AuditEvent)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if cursor:
        stmt = stmt.where(AuditEvent.id > cursor)
    stmt = stmt.order_by(AuditEvent.id).limit(limit)
    rows = list(db.execute(stmt).scalars())
    return {
        "items": [
            {
                "id": e.id,
                "ts": e.ts.isoformat() if e.ts else None,
                "actor_id": e.actor_id,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "summary": e.summary_json,
            }
            for e in rows
        ],
        "next_cursor": rows[-1].id if rows else None,
    }


@router.get("/audit/verify")
def verify_audit(
    _op: Operator = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    status = AuditService(db).verify()
    return {
        "valid": status.valid,
        "events": status.events,
        "first_broken_id": status.first_broken_id,
    }
