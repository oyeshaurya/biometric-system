"""Retention and deletion sweeps (FR-16, FR-22).

Deletes expired debug frames (if the feature was ever enabled) and templates past the
configured retention period. ``dry_run`` reports counts without deleting anything.
"""

from __future__ import annotations

import os
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.db.models import DebugFrame, Template, utcnow
from biometric_lab.services.audit import AuditService
from biometric_lab.services.settings import TEMPLATE_RETENTION_DAYS, SettingsService


class RetentionService:
    def __init__(
        self, session: Session, settings_svc: SettingsService, audit: AuditService
    ) -> None:
        self.session = session
        self.settings_svc = settings_svc
        self.audit = audit

    def sweep(self, *, dry_run: bool = True, actor_id: int | None = None) -> dict:
        now = utcnow()

        expired_frames = list(
            self.session.execute(
                select(DebugFrame).where(DebugFrame.expires_at < now)
            ).scalars()
        )
        debug_deleted = 0
        for frame in expired_frames:
            if not dry_run:
                try:
                    if frame.path and os.path.exists(frame.path):
                        os.remove(frame.path)
                except OSError:
                    pass
                self.session.delete(frame)
            debug_deleted += 1

        templates_deleted = 0
        retention_days = self.settings_svc.get_int(TEMPLATE_RETENTION_DAYS, 0)
        if retention_days > 0:
            cutoff = now - timedelta(days=retention_days)
            old_templates = list(
                self.session.execute(
                    select(Template).where(Template.created_at < cutoff)
                ).scalars()
            )
            for template in old_templates:
                if not dry_run:
                    self.session.delete(template)
                templates_deleted += 1

        if not dry_run:
            self.session.flush()
            self.audit.append(
                "retention.swept",
                actor_id=actor_id,
                entity_type="system",
                summary={
                    "debug_frames_deleted": debug_deleted,
                    "templates_deleted": templates_deleted,
                },
            )
        return {
            "dry_run": dry_run,
            "debug_frames_deleted": debug_deleted,
            "templates_deleted": templates_deleted,
        }
