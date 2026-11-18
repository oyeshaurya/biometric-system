"""Cosine matcher with max fusion over templates (AD-3, SYSTEM_DESIGN.md 8.1)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from biometric_lab.core.matching.base import MatchError


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        raise MatchError("cannot score a zero-length embedding")
    return float(np.dot(a, b) / (na * nb))


class CosineMatcher:
    """Score = maximum cosine similarity between the probe and any enrolled template."""

    name = "cosine_max"

    def score(self, probe: np.ndarray, templates: Sequence[np.ndarray]) -> float:
        if not templates:
            raise MatchError("no templates to match against")
        return max(cosine_similarity(probe, t) for t in templates)
