"""Liveness protocol and result type (FR-14, SYSTEM_DESIGN.md section 7).

Liveness is a SEPARATE function from identity verification. Its result never enters the
identity score. The default checker reports "not run".
"""

from __future__ import annotations

from typing import Protocol, TypedDict

import numpy as np


class LivenessResult(TypedDict):
    method: str
    score: float | None
    passed: bool | None
    reason: str | None


class LivenessUnavailable(Exception):
    """Raised when a configured liveness method cannot run."""


class LivenessChecker(Protocol):
    method: str

    def check(self, image_bgr: np.ndarray) -> LivenessResult:
        ...
