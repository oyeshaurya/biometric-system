"""Runs and trials (FR-07, FR-08, FR-08a, FR-09, NFR-11).

Ground truth is derived on the server from the labels. A trial and its audit event are
written in the same transaction (the caller's session_scope commits both together).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.context import AppContext
from biometric_lab.db.models import Run, Trial, utcnow
from biometric_lab.services.audit import AuditService
from biometric_lab.services.participants import ConsentInactive, ParticipantService
from biometric_lab.services.settings import SettingsService
from biometric_lab.services.verification import NO_TEMPLATES, VerificationService, VerifyResult


class RunError(Exception):
    pass


@dataclass
class TrialOutcome:
    trial: Trial
    warnings: list[str]


class TrialService:
    def __init__(
        self,
        session: Session,
        ctx: AppContext,
        participants: ParticipantService,
        verification: VerificationService,
        audit: AuditService,
        settings_svc: SettingsService,
    ) -> None:
        self.session = session
        self.ctx = ctx
        self.participants = participants
        self.verification = verification
        self.audit = audit
        self.settings_svc = settings_svc

    # --- runs ----------------------------------------------------------------
    def _config_hash(self) -> str:
        blob = json.dumps(self.settings_svc.all(), sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def create_run(
        self, name: str, *, description: str | None = None, actor_id: int | None = None
    ) -> Run:
        if self.session.execute(select(Run).where(Run.name == name)).scalar_one_or_none():
            raise RunError(f"run name '{name}' already exists")
        info = self.ctx.engine.info
        run = Run(
            name=name,
            description=description,
            threshold_snapshot=self.settings_svc.operating_threshold(),
            model_name=info["model_name"],
            model_version=info["model_version"],
            config_hash=self._config_hash(),
            status="open",
        )
        self.session.add(run)
        self.session.flush()
        self.audit.append(
            "run.created",
            actor_id=actor_id,
            entity_type="run",
            entity_id=run.id,
            summary={"name": name, "threshold": run.threshold_snapshot},
        )
        return run

    def get_run(self, run_id: int) -> Run:
        run = self.session.get(Run, run_id)
        if run is None or run.status == "deleted":
            raise RunError(f"run {run_id} not found")
        return run

    def list_runs(self) -> list[Run]:
        return list(
            self.session.execute(
                select(Run).where(Run.status != "deleted").order_by(Run.id.desc())
            ).scalars()
        )

    def close_run(self, run_id: int, *, actor_id: int | None = None) -> Run:
        run = self.get_run(run_id)
        run.status = "closed"
        run.closed_at = utcnow()
        self.session.flush()
        self.audit.append(
            "run.closed", actor_id=actor_id, entity_type="run", entity_id=run.id, summary={}
        )
        return run

    def delete_run(self, run_id: int, *, confirm: str, actor_id: int | None = None) -> dict:
        run = self.get_run(run_id)
        if confirm != run.name:
            raise RunError("confirmation does not match run name")
        trials = list(
            self.session.execute(select(Trial).where(Trial.run_id == run.id)).scalars()
        )
        count = len(trials)
        for t in trials:
            self.session.delete(t)
        self.session.delete(run)
        self.session.flush()
        self.audit.append(
            "run.deleted",
            actor_id=actor_id,
            entity_type="run",
            entity_id=run_id,
            summary={"name": run.name, "trials_deleted": count},
        )
        return {"trials_deleted": count}

    # --- trials --------------------------------------------------------------
    def record(
        self,
        run_id: int,
        *,
        probe_label: str,
        claimed_label: str,
        image: np.ndarray,
        condition_tags: list[str],
        ground_truth_hint: str | None = None,
        run_liveness: bool = False,
        actor_id: int | None = None,
    ) -> TrialOutcome:
        run = self.get_run(run_id)
        if run.status != "open":
            raise RunError(f"run {run_id} is not open")

        ground_truth = "genuine" if probe_label == claimed_label else "impostor"
        warnings: list[str] = []
        if ground_truth_hint and ground_truth_hint != ground_truth:
            warnings.append("ground_truth_overridden")

        claimed = self.participants.get_by_label(claimed_label)
        probe = self.participants.get_by_label(probe_label)
        info = self.ctx.engine.info

        start = time.perf_counter()
        if claimed is None:
            result = VerifyResult(
                outcome="fta",
                score=None,
                threshold=self.settings_svc.operating_threshold(),
                decision=None,
                template_count=0,
                quality=None,
                fta_reason=NO_TEMPLATES,
                liveness=self.ctx.liveness.check(image) if run_liveness else None,
            )
        else:
            try:
                self.participants.require_active_consent(claimed.id)
            except ConsentInactive as exc:
                raise RunError(f"claimed participant '{claimed_label}' has no active consent") from exc
            result = self.verification.verify(claimed, image, run_liveness=run_liveness)
        duration_ms = int((time.perf_counter() - start) * 1000)

        liveness = result.liveness or {}
        trial = Trial(
            run_id=run.id,
            probe_label=probe_label,
            claimed_label=claimed_label,
            probe_participant_id=probe.id if probe else None,
            claimed_participant_id=claimed.id if claimed else None,
            ground_truth=ground_truth,
            outcome=result.outcome,
            score=result.score,
            threshold=result.threshold,
            fta_reason=result.fta_reason,
            template_count=result.template_count,
            condition_tags=condition_tags,
            model_name=info["model_name"],
            model_version=info["model_version"],
            liveness_method=liveness.get("method"),
            liveness_score=liveness.get("score"),
            liveness_passed=liveness.get("passed"),
            duration_ms=duration_ms,
        )
        self.session.add(trial)
        self.session.flush()
        self.audit.append(
            "trial.created",
            actor_id=actor_id,
            entity_type="trial",
            entity_id=trial.id,
            summary={
                "run_id": run.id,
                "ground_truth": ground_truth,
                "outcome": result.outcome,
                "score": result.score,
            },
        )
        return TrialOutcome(trial=trial, warnings=warnings)
