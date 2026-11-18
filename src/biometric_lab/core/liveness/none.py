"""No-op liveness checker: always reports 'not run' (FR-14 default)."""

from __future__ import annotations

import numpy as np

from biometric_lab.core.liveness.base import LivenessResult


class NoLiveness:
    method = "none"

    def check(self, image_bgr: np.ndarray) -> LivenessResult:
        return {"method": self.method, "score": None, "passed": None, "reason": "not_run"}
