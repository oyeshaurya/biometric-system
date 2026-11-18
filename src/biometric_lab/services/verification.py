"""1:1 verification (FR-05, FR-09, SYSTEM_DESIGN.md section 4).

Ordering: the caller checks consent BEFORE passing an image here. This service runs the
quality gate, decrypts active templates in memory, scores, and decides. It never persists
anything and never returns the embedding.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.context import AppContext
from biometric_lab.core.face.quality import check_quality
from biometric_lab.core.liveness.base import LivenessResult
from biometric_lab.db.models import Participant, Template
from biometric_lab.services.settings import SettingsService

NO_TEMPLATES = "NO_TEMPLATES"


@dataclass
class VerifyResult:
    outcome: str  # "accept" | "reject" | "fta"
    score: float | None
    threshold: float
    decision: str | None  # "accept" | "reject"; None for fta
    template_count: int
    quality: dict | None
    fta_reason: str | None
    liveness: LivenessResult | None

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "score": self.score,
            "threshold": self.threshold,
            "decision": self.decision,
            "template_count": self.template_count,
            "quality": self.quality,
            "fta_reason": self.fta_reason,
            "liveness": self.liveness,
        }


class VerificationService:
    def __init__(self, session: Session, ctx: AppContext, settings_svc: SettingsService) -> None:
        self.session = session
        self.ctx = ctx
        self.settings_svc = settings_svc

    def active_templates(self, participant_id: int) -> list[np.ndarray]:
        rows = self.session.execute(
            select(Template).where(
                Template.participant_id == participant_id, Template.deleted_at.is_(None)
            )
        ).scalars()
        return [self.ctx.cipher.decrypt_vector(r.vector_enc) for r in rows]

    def verify(
        self,
        participant: Participant,
        image: np.ndarray,
        *,
        threshold: float | None = None,
        run_liveness: bool = False,
    ) -> VerifyResult:
        thr = self.settings_svc.operating_threshold() if threshold is None else float(threshold)
        liveness: LivenessResult | None = (
            self.ctx.liveness.check(image) if run_liveness else None
        )

        detections = self.ctx.engine.analyse(image)
        q = check_quality(detections, **self.settings_svc.quality_params())
        if not q.ok or q.detection is None or q.detection.embedding is None:
            return VerifyResult(
                outcome="fta",
                score=None,
                threshold=thr,
                decision=None,
                template_count=0,
                quality=None,
                fta_reason=q.reason,
                liveness=liveness,
            )

        templates = self.active_templates(participant.id)
        if not templates:
            return VerifyResult(
                outcome="fta",
                score=None,
                threshold=thr,
                decision=None,
                template_count=0,
                quality=q.detection.quality_summary(),
                fta_reason=NO_TEMPLATES,
                liveness=liveness,
            )

        score = self.ctx.matcher.score(q.detection.embedding, templates)
        decision = "accept" if score >= thr else "reject"
        return VerifyResult(
            outcome=decision,
            score=float(score),
            threshold=thr,
            decision=decision,
            template_count=len(templates),
            quality=q.detection.quality_summary(),
            fta_reason=None,
            liveness=liveness,
        )
