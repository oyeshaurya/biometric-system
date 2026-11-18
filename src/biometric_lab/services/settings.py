"""Runtime settings with mandatory reason and audit (FR-06, FR-17).

Infrastructure defaults come from :class:`biometric_lab.config.Settings`; tunable study
parameters live in the ``settings`` table so an admin can change them with a recorded
reason. ``seed_defaults`` populates the table on first run.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.config import DEFAULT_CONDITION_GROUPS, Settings
from biometric_lab.db.models import Setting
from biometric_lab.services.audit import AuditService

# Setting keys
OPERATING_THRESHOLD = "operating_threshold"
QUALITY_MIN_DET_SCORE = "quality.min_det_score"
QUALITY_MIN_FACE_PX = "quality.min_face_px"
QUALITY_MAX_YAW_DEG = "quality.max_yaw_deg"
CONDITION_GROUPS = "condition_groups"
TEMPLATE_RETENTION_DAYS = "template_retention_days"
DEBUG_FRAMES_ENABLED = "debug_frames_enabled"
LIVENESS_ENABLED = "liveness_enabled"


class SettingsError(Exception):
    pass


class SettingsService:
    def __init__(self, session: Session, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    def get(self, key: str, default: Any = None) -> Any:
        row = self.session.get(Setting, key)
        return row.value_json if row is not None else default

    def get_float(self, key: str, default: float) -> float:
        return float(self.get(key, default))

    def get_int(self, key: str, default: int) -> int:
        return int(self.get(key, default))

    def get_bool(self, key: str, default: bool) -> bool:
        return bool(self.get(key, default))

    def all(self) -> dict[str, Any]:
        rows = self.session.execute(select(Setting)).scalars()
        return {row.key: row.value_json for row in rows}

    def operating_threshold(self) -> float:
        return self.get_float(OPERATING_THRESHOLD, 0.30)

    def quality_params(self) -> dict[str, Any]:
        return {
            "min_det_score": self.get_float(QUALITY_MIN_DET_SCORE, 0.60),
            "min_face_px": self.get_int(QUALITY_MIN_FACE_PX, 80),
            "max_yaw_deg": self.get_float(QUALITY_MAX_YAW_DEG, 30.0),
        }

    def set(
        self,
        key: str,
        value: Any,
        *,
        reason: str,
        actor_id: int | None = None,
    ) -> dict[str, Any]:
        if not reason or not reason.strip():
            raise SettingsError("a reason is required to change a setting")
        if key == OPERATING_THRESHOLD and not (-1.0 <= float(value) <= 1.0):
            raise SettingsError("operating_threshold must be in [-1, 1]")
        row = self.session.get(Setting, key)
        old = row.value_json if row else None
        if row is None:
            row = Setting(key=key, value_json=value, reason=reason, updated_by=actor_id)
            self.session.add(row)
        else:
            row.value_json = value
            row.reason = reason
            row.updated_by = actor_id
        self.session.flush()
        self.audit.append(
            "settings.changed",
            actor_id=actor_id,
            entity_type="setting",
            entity_id=key,
            summary={"key": key, "old": old, "new": value, "reason": reason},
        )
        return {"key": key, "old": old, "new": value}

    def seed_defaults(self, settings: Settings) -> None:
        """Populate missing settings from config defaults (no audit; reason 'initial')."""
        defaults = {
            OPERATING_THRESHOLD: settings.operating_threshold_default,
            QUALITY_MIN_DET_SCORE: settings.quality_min_det_score,
            QUALITY_MIN_FACE_PX: settings.quality_min_face_px,
            QUALITY_MAX_YAW_DEG: settings.quality_max_yaw_deg,
            CONDITION_GROUPS: DEFAULT_CONDITION_GROUPS,
            TEMPLATE_RETENTION_DAYS: settings.template_retention_days,
            DEBUG_FRAMES_ENABLED: settings.debug_frames_enabled,
            LIVENESS_ENABLED: False,
        }
        for key, value in defaults.items():
            if self.session.get(Setting, key) is None:
                self.session.add(Setting(key=key, value_json=value, reason="initial"))
        self.session.flush()
