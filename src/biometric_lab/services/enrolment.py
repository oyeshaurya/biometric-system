"""Enrolment: quality-gated capture to encrypted templates (FR-03, FR-03a, FR-20)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.context import AppContext
from biometric_lab.core.face.quality import check_quality
from biometric_lab.db.models import Participant, Template, utcnow
from biometric_lab.services.audit import AuditService
from biometric_lab.services.settings import SettingsService


class EnrolmentError(Exception):
    pass


@dataclass
class EnrolmentOutcome:
    batch_id: str
    accepted: int
    rejected: list[dict] = field(default_factory=list)
    templates: list[dict] = field(default_factory=list)


class EnrolmentService:
    def __init__(
        self,
        session: Session,
        ctx: AppContext,
        audit: AuditService,
        settings_svc: SettingsService,
    ) -> None:
        self.session = session
        self.ctx = ctx
        self.audit = audit
        self.settings_svc = settings_svc

    def enrol(
        self,
        participant: Participant,
        frames: list[np.ndarray],
        *,
        replace: bool = False,
        actor_id: int | None = None,
    ) -> EnrolmentOutcome:
        min_frames = self.ctx.settings.enrol_min_frames
        max_frames = self.ctx.settings.enrol_max_frames
        if not frames:
            raise EnrolmentError("no frames supplied")
        if len(frames) > max_frames:
            raise EnrolmentError(f"too many frames ({len(frames)} > {max_frames})")

        qp = self.settings_svc.quality_params()
        batch_id = str(uuid.uuid4())
        accepted: list[tuple[np.ndarray, dict]] = []
        rejected: list[dict] = []

        for idx, frame in enumerate(frames):
            detections = self.ctx.engine.analyse(frame)
            q = check_quality(detections, **qp)
            if not q.ok or q.detection is None or q.detection.embedding is None:
                rejected.append({"index": idx, "reason": q.reason or "NO_FACE"})
                continue
            accepted.append((q.detection.embedding, q.detection.quality_summary()))

        if len(accepted) < min_frames:
            raise EnrolmentError(
                f"only {len(accepted)} usable frame(s); at least {min_frames} required"
            )

        if replace:
            self._soft_delete_active(participant.id)

        info = self.ctx.engine.info
        created: list[dict] = []
        for embedding, quality in accepted:
            template = Template(
                participant_id=participant.id,
                enrolment_batch_id=batch_id,
                model_name=info["model_name"],
                model_version=info["model_version"],
                dim=info["dim"],
                vector_enc=self.ctx.cipher.encrypt_vector(embedding),
                quality_json=quality,
            )
            self.session.add(template)
            self.session.flush()
            created.append({"id": template.id, "quality": quality})

        self.audit.append(
            "enrolment.completed",
            actor_id=actor_id,
            entity_type="participant",
            entity_id=participant.id,
            summary={
                "batch_id": batch_id,
                "accepted": len(created),
                "rejected": len(rejected),
                "replace": replace,
                "model": info["model_name"],
            },
        )
        return EnrolmentOutcome(
            batch_id=batch_id, accepted=len(created), rejected=rejected, templates=created
        )

    def _soft_delete_active(self, participant_id: int) -> None:
        rows = self.session.execute(
            select(Template).where(
                Template.participant_id == participant_id, Template.deleted_at.is_(None)
            )
        ).scalars()
        now = utcnow()
        for t in rows:
            t.deleted_at = now
        self.session.flush()
