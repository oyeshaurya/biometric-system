"""Participants, consent, enrolment and template deletion routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from biometric_lab.api.deps import current_operator, get_context, get_db, require_admin, verify_csrf
from biometric_lab.api.images import decode_request_image
from biometric_lab.context import AppContext
from biometric_lab.db.models import Operator
from biometric_lab.schemas import ConsentCreate, EnrolRequest, ParticipantCreate, ReasonRequest
from biometric_lab.services.audit import AuditService
from biometric_lab.services.enrolment import EnrolmentService
from biometric_lab.services.participants import ParticipantService
from biometric_lab.services.settings import SettingsService

router = APIRouter(tags=["participants"])


def _participants(db: Session, ctx: AppContext) -> tuple[AuditService, ParticipantService]:
    audit = AuditService(db)
    return audit, ParticipantService(db, ctx, audit)


@router.post("/participants")
def create_participant(
    body: ParticipantCreate,
    op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    _, participants = _participants(db, ctx)
    p = participants.create(body.subject_code, display_name=body.display_name, actor_id=op.id)
    return {"id": p.id, "subject_code": p.subject_code, "status": p.status, "alias": p.alias}


@router.get("/participants")
def list_participants(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    _, participants = _participants(db, ctx)
    items = participants.list(status=status, q=q)
    return {
        "items": [
            {"id": p.id, "subject_code": p.subject_code, "status": p.status, "alias": p.alias}
            for p in items
        ],
        "total": len(items),
    }


@router.get("/participants/{participant_id}")
def get_participant(
    participant_id: int,
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    _, participants = _participants(db, ctx)
    p = participants.get(participant_id)
    consent = participants.active_consent(participant_id)
    template_count = len([t for t in p.templates if t.deleted_at is None])
    return {
        "id": p.id,
        "subject_code": p.subject_code,
        "status": p.status,
        "alias": p.alias,
        "consent": {"version": consent.consent_version, "granted_at": consent.granted_at.isoformat()}
        if consent
        else None,
        "template_count": template_count,
    }


@router.post("/participants/{participant_id}/consent")
def add_consent(
    participant_id: int,
    body: ConsentCreate,
    op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    _, participants = _participants(db, ctx)
    consent = participants.record_consent(
        participant_id,
        consent_version=body.consent_version,
        consent_text_sha256=body.consent_text_sha256,
        purposes=body.purposes,
        accepted=body.accepted,
        actor_id=op.id,
    )
    return {"id": consent.id, "granted_at": consent.granted_at.isoformat(), "accepted": body.accepted}


@router.post("/participants/{participant_id}/consent/withdraw")
def withdraw_consent(
    participant_id: int,
    body: ReasonRequest,
    op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    _, participants = _participants(db, ctx)
    return participants.withdraw_consent(participant_id, reason=body.reason, actor_id=op.id)


@router.delete("/participants/{participant_id}")
def delete_participant(
    participant_id: int,
    mode: str = Query(default="anonymise"),
    op: Operator = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    _, participants = _participants(db, ctx)
    return participants.delete(participant_id, mode=mode, actor_id=op.id)


@router.post("/participants/{participant_id}/enrolment")
def enrol(
    participant_id: int,
    body: EnrolRequest,
    op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    audit, participants = _participants(db, ctx)
    settings_svc = SettingsService(db, audit)
    participant = participants.get(participant_id)
    participants.require_active_consent(participant_id)
    frames = [decode_request_image(ctx, f.image_b64) for f in body.frames]
    service = EnrolmentService(db, ctx, audit, settings_svc)
    outcome = service.enrol(participant, frames, replace=body.replace, actor_id=op.id)
    return {
        "batch_id": outcome.batch_id,
        "accepted": outcome.accepted,
        "rejected": outcome.rejected,
        "templates": outcome.templates,
    }


@router.post("/participants/{participant_id}/templates/delete")
def delete_templates(
    participant_id: int,
    body: ReasonRequest,
    op: Operator = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    audit, participants = _participants(db, ctx)
    participant = participants.get(participant_id)
    deleted = participants._hard_delete_templates(participant.id)
    audit.append(
        "templates.deleted",
        actor_id=op.id,
        entity_type="participant",
        entity_id=participant.id,
        summary={"deleted": deleted, "reason": body.reason},
    )
    return {"deleted": deleted}
