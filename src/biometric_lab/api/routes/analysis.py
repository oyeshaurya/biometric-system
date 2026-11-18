"""Metrics, by-condition, sweep and subject bootstrap (FR-10, FR-11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from biometric_lab.api.deps import current_operator, get_db
from biometric_lab.db.models import Operator
from biometric_lab.services.metrics import MetricsService

router = APIRouter(tags=["analysis"])


@router.get("/runs/{run_id}/metrics")
def metrics(
    run_id: int,
    threshold: float | None = Query(default=None),
    tag: str | None = Query(default=None),
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
) -> dict:
    return MetricsService(db).report(run_id, threshold=threshold, tag=tag)


@router.get("/runs/{run_id}/metrics/by-condition")
def by_condition(
    run_id: int,
    threshold: float | None = Query(default=None),
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
) -> dict:
    return MetricsService(db).by_condition(run_id, threshold=threshold)


@router.get("/runs/{run_id}/sweep")
def sweep(
    run_id: int,
    tag: str | None = Query(default=None),
    max_points: int = Query(default=1000, ge=0, le=20000),
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
) -> dict:
    return MetricsService(db).sweep(run_id, tag=tag, max_points=max_points)


@router.get("/runs/{run_id}/bootstrap")
def bootstrap(
    run_id: int,
    threshold: float | None = Query(default=None),
    iterations: int = Query(default=2000, ge=100, le=10000),
    _op: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
) -> dict:
    return MetricsService(db).subject_bootstrap(
        run_id, threshold=threshold, iterations=iterations
    )
