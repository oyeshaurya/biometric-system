"""Verification, preview and liveness routes (FR-05, FR-14)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from biometric_lab.api.deps import current_operator, get_context, get_db, verify_csrf
from biometric_lab.api.errors import ProblemError
from biometric_lab.api.images import decode_request_image
from biometric_lab.context import AppContext
from biometric_lab.core.face.quality import check_quality
from biometric_lab.db.models import Operator
from biometric_lab.schemas import LivenessRequest, PreviewRequest, VerifyRequest
from biometric_lab.services.audit import AuditService
from biometric_lab.services.participants import ParticipantService
from biometric_lab.services.settings import LIVENESS_ENABLED, SettingsService
from biometric_lab.services.verification import VerificationService

router = APIRouter(tags=["verify"])


@router.post("/verify")
def verify(
    body: VerifyRequest,
    op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    audit = AuditService(db)
    participants = ParticipantService(db, ctx, audit)
    settings_svc = SettingsService(db, audit)
    participant = participants.get(body.claimed_participant_id)
    participants.require_active_consent(participant.id)

    image = decode_request_image(ctx, body.image_b64)
    service = VerificationService(db, ctx, settings_svc)
    result = service.verify(
        participant, image, threshold=body.threshold, run_liveness=body.liveness
    )
    audit.append(
        "verify.performed",
        actor_id=op.id,
        entity_type="participant",
        entity_id=participant.id,
        summary={"outcome": result.outcome, "score": result.score, "threshold": result.threshold},
    )
    if result.outcome == "fta":
        raise ProblemError(422, result.fta_reason or "FTA", "no usable face captured")
    return result.as_dict()


@router.post("/verify/preview")
def preview(
    body: PreviewRequest,
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    audit = AuditService(db)
    settings_svc = SettingsService(db, audit)
    image = decode_request_image(ctx, body.image_b64)
    detections = ctx.engine.analyse(image)
    q = check_quality(detections, **settings_svc.quality_params())
    first = detections[0] if detections else None
    return {
        "faces": len(detections),
        "det_score": first.det_score if first else None,
        "bbox": list(first.bbox) if first else None,
        "yaw_deg": first.yaw_deg if first else None,
        "guidance": q.guidance(),
    }


@router.post("/liveness/check")
def liveness_check(
    body: LivenessRequest,
    _op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    audit = AuditService(db)
    settings_svc = SettingsService(db, audit)
    if not settings_svc.get_bool(LIVENESS_ENABLED, False):
        raise ProblemError(503, "LIVENESS_UNAVAILABLE", "liveness is disabled in settings")
    image = decode_request_image(ctx, body.image_b64)
    return dict(ctx.liveness.check(image))
