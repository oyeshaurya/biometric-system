"""Typed application configuration (ARCHITECTURE.md section 7).

Infrastructure settings (paths, secrets, engine choice) come from the environment or a
``.env`` file. Tunable study parameters (operating threshold, quality-gate thresholds,
condition vocabulary) have defaults here but are overridden at runtime by the ``settings``
table via :class:`biometric_lab.services.settings.SettingsService`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Controlled vocabulary for condition tags (FR-08, FR-03a). Tags are "group:value".
DEFAULT_CONDITION_GROUPS: dict[str, list[str]] = {
    "lighting": ["normal", "bright", "dim", "backlit"],
    "distance": ["near", "medium", "far"],
    "glasses": ["on", "off"],
    "pose": ["frontal", "turned"],
    "expression": ["neutral", "smiling"],
    "background": ["plain", "busy"],
    "camera": ["builtin", "external"],
}


class Settings(BaseSettings):
    """Infrastructure and default study configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BIOMETRIC_LAB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Infrastructure
    key_file: Path = Field(default=Path("../biometric_lab.key"))
    db_url: str = "sqlite:///data/biometric.db"
    host: str = "127.0.0.1"
    port: int = 8000
    session_secret: str = "change-me-to-a-long-random-string"
    engine: str = "fake"  # fake | insightface | yunet_sface

    # Default tunable study parameters (seeded into the settings table on first run)
    operating_threshold_default: float = 0.30
    quality_min_det_score: float = 0.60
    quality_min_face_px: int = 80
    quality_max_yaw_deg: float = 30.0
    enrol_min_frames: int = 3
    enrol_max_frames: int = 10

    # Retention
    template_retention_days: int = 0  # 0 disables the template sweep
    debug_frames_enabled: bool = False
    debug_frame_max_age_hours: int = 24

    # Limits
    max_image_bytes: int = 2 * 1024 * 1024
    max_image_dim: int = 1920
    small_sample_floor: int = 30

    @property
    def is_loopback(self) -> bool:
        return self.host in {"127.0.0.1", "localhost", "::1"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
