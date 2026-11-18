"""Face engine protocol and data types (ARCHITECTURE.md section 5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypedDict, runtime_checkable

import numpy as np


class ModelInfo(TypedDict):
    detector: str
    recogniser: str
    model_name: str
    model_version: str
    dim: int


class FaceEngineError(Exception):
    """Raised when the engine cannot run (model missing, bad input)."""


@dataclass
class FaceDetection:
    """One detected face. ``bbox`` is (x, y, width, height) in pixels."""

    bbox: tuple[float, float, float, float]
    det_score: float
    yaw_deg: float
    embedding: np.ndarray | None = None
    extra: dict = field(default_factory=dict)

    @property
    def min_side_px(self) -> float:
        return float(min(self.bbox[2], self.bbox[3]))

    def quality_summary(self) -> dict:
        """Non-biometric quality fields safe to persist in ``templates.quality_json``."""
        return {
            "det_score": round(float(self.det_score), 4),
            "min_side_px": round(self.min_side_px, 1),
            "yaw_deg": round(float(self.yaw_deg), 2),
        }


@runtime_checkable
class FaceEngine(Protocol):
    info: ModelInfo

    def analyse(self, image_bgr: np.ndarray) -> list[FaceDetection]:
        """Return all detected faces with embeddings, or an empty list if none."""
        ...
