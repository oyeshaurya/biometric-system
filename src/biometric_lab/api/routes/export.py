"""CSV export routes (FR-13)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from biometric_lab.api.deps import current_operator, get_db
from biometric_lab.db.models import Operator
from biometric_lab.services.audit import AuditService
from biometric_lab.services.export import ExportService
from biometric_lab.services.metrics import MetricsService

router = APIRouter(tags=["export"])


def _export(db: Session) -> ExportService:
    return ExportService(db, AuditService(db), MetricsService(db))


def _csv(content: str, filename: str) -> PlainTextResponse:
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/runs/{run_id}/export/trials.csv")
def export_trials(
    run_id: int, op: Operator = Depends(current_operator), db: Session = Depends(get_db)
) -> PlainTextResponse:
    return _csv(_export(db).trials_csv(run_id, actor_id=op.id), f"run{run_id}_trials.csv")


@router.get("/runs/{run_id}/export/metrics.csv")
def export_metrics(
    run_id: int,
    tag: str | None = Query(default=None),
    op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    return _csv(_export(db).metrics_csv(run_id, tag=tag, actor_id=op.id), f"run{run_id}_metrics.csv")


@router.get("/runs/{run_id}/export/sweep.csv")
def export_sweep(
    run_id: int,
    tag: str | None = Query(default=None),
    op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    return _csv(_export(db).sweep_csv(run_id, tag=tag, actor_id=op.id), f"run{run_id}_sweep.csv")
