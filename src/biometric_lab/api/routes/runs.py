"""Runs and trials routes (FR-07, FR-08)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from biometric_lab.api.deps import current_operator, get_context, get_db, require_admin, verify_csrf
from biometric_lab.api.images import decode_request_image
from biometric_lab.context import AppContext
from biometric_lab.db.models import Operator, Trial
from biometric_lab.schemas import ConfirmRequest, RunCreate, TrialCreate
from biometric_lab.services.audit import AuditService
from biometric_lab.services.participants import ParticipantService
from biometric_lab.services.settings import SettingsService
from biometric_lab.services.trials import TrialService
from biometric_lab.services.verification import VerificationService

router = APIRouter(tags=["runs"])


def _trial_service(db: Session, ctx: AppContext) -> TrialService:
    audit = AuditService(db)
    participants = ParticipantService(db, ctx, audit)
    settings_svc = SettingsService(db, audit)
    verification = VerificationService(db, ctx, settings_svc)
    return TrialService(db, ctx, participants, verification, audit, settings_svc)


def _trial_dict(t: Trial) -> dict:
    return {
        "id": t.id,
        "run_id": t.run_id,
        "probe_label": t.probe_label,
        "claimed_label": t.claimed_label,
        "ground_truth": t.ground_truth,
        "outcome": t.outcome,
        "score": t.score,
        "threshold": t.threshold,
        "fta_reason": t.fta_reason,
        "template_count": t.template_count,
        "condition_tags": t.condition_tags,
        "liveness_method": t.liveness_method,
        "liveness_score": t.liveness_score,
        "liveness_passed": t.liveness_passed,
        "duration_ms": t.duration_ms,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.post("/runs")
def create_run(
    body: RunCreate,
    op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    run = _trial_service(db, ctx).create_run(body.name, description=body.description, actor_id=op.id)
    return {
        "id": run.id,
        "name": run.name,
        "threshold_snapshot": run.threshold_snapshot,
        "model": {"name": run.model_name, "version": run.model_version},
        "status": run.status,
    }


@router.get("/runs")
def list_runs(
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    runs = _trial_service(db, ctx).list_runs()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "status": r.status,
                "trial_count": len(r.trials),
                "threshold_snapshot": r.threshold_snapshot,
            }
            for r in runs
        ]
    }


@router.post("/runs/{run_id}/close")
def close_run(
    run_id: int,
    op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    run = _trial_service(db, ctx).close_run(run_id, actor_id=op.id)
    return {"closed_at": run.closed_at.isoformat() if run.closed_at else None}


@router.delete("/runs/{run_id}")
def delete_run(
    run_id: int,
    body: ConfirmRequest,
    op: Operator = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    return _trial_service(db, ctx).delete_run(run_id, confirm=body.confirm, actor_id=op.id)


@router.post("/runs/{run_id}/trials")
def create_trial(
    run_id: int,
    body: TrialCreate,
    op: Operator = Depends(current_operator),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    image = decode_request_image(ctx, body.image_b64)
    outcome = _trial_service(db, ctx).record(
        run_id,
        probe_label=body.probe_label,
        claimed_label=body.claimed_label,
        image=image,
        condition_tags=body.condition_tags,
        ground_truth_hint=body.ground_truth_hint,
        run_liveness=body.liveness,
        actor_id=op.id,
    )
    data = _trial_dict(outcome.trial)
    data["warnings"] = outcome.warnings
    return data


@router.get("/runs/{run_id}/trials")
def list_trials(
    run_id: int,
    ground_truth: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    cursor: int = Query(default=0),
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    ctx: AppContext = Depends(get_context),
) -> dict:
    from sqlalchemy import select

    stmt = select(Trial).where(Trial.run_id == run_id)
    if ground_truth:
        stmt = stmt.where(Trial.ground_truth == ground_truth)
    if outcome:
        stmt = stmt.where(Trial.outcome == outcome)
    if cursor:
        stmt = stmt.where(Trial.id > cursor)
    stmt = stmt.order_by(Trial.id).limit(limit + 1)
    rows = list(db.execute(stmt).scalars())
    if tag:
        rows = [r for r in rows if tag in (r.condition_tags or [])]
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [_trial_dict(t) for t in rows],
        "next_cursor": rows[-1].id if rows and has_more else None,
    }


@router.get("/trials/{trial_id}")
def get_trial(
    trial_id: int,
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
) -> dict:
    from biometric_lab.api.errors import ProblemError

    t = db.get(Trial, trial_id)
    if t is None:
        raise ProblemError(404, "NOT_FOUND", "trial not found")
    return _trial_dict(t)
