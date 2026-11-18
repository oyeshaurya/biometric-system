"""Error-rate definitions (SYSTEM_DESIGN.md section 8.2).

Decision rule, used everywhere: **accept if score >= threshold**.

Definitions (FTA trials are excluded by the caller before these functions see the data):
    FAR(t) = count(impostor_score >= t) / n_impostor     (impostor wrongly accepted)
    FRR(t) = count(genuine_score  <  t) / n_genuine       (genuine wrongly rejected)
    GAR(t) = 1 - FRR(t)
    accuracy = (TP + TN) / (n_genuine + n_impostor)
    balanced_accuracy = (GAR + (1 - FAR)) / 2

A rate is ``None`` when its denominator is zero (an empty test class).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EMPTY_CLASS = "EMPTY_CLASS"


def _as_array(scores: object) -> np.ndarray:
    arr = np.asarray(scores, dtype=np.float64).ravel()
    return arr


def far(impostor_scores: object, threshold: float) -> float | None:
    """False acceptance rate at ``threshold``, or ``None`` if there are no impostors."""
    arr = _as_array(impostor_scores)
    if arr.size == 0:
        return None
    return float(np.count_nonzero(arr >= threshold) / arr.size)


def frr(genuine_scores: object, threshold: float) -> float | None:
    """False rejection rate at ``threshold``, or ``None`` if there are no genuine trials."""
    arr = _as_array(genuine_scores)
    if arr.size == 0:
        return None
    return float(np.count_nonzero(arr < threshold) / arr.size)


def gar(genuine_scores: object, threshold: float) -> float | None:
    """Genuine acceptance rate = 1 - FRR."""
    value = frr(genuine_scores, threshold)
    return None if value is None else 1.0 - value


@dataclass(frozen=True)
class RateReport:
    """All decision-based rates at one threshold."""

    threshold: float
    n_genuine: int
    n_impostor: int
    far: float | None
    frr: float | None
    gar: float | None
    accuracy: float | None
    balanced_accuracy: float | None
    warnings: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "threshold": self.threshold,
            "n_genuine": self.n_genuine,
            "n_impostor": self.n_impostor,
            "far": self.far,
            "frr": self.frr,
            "gar": self.gar,
            "accuracy": self.accuracy,
            "balanced_accuracy": self.balanced_accuracy,
            "warnings": list(self.warnings),
        }


def rate_report(
    genuine_scores: object,
    impostor_scores: object,
    threshold: float,
    *,
    small_sample_floor: int = 30,
) -> RateReport:
    """Compute FAR, FRR, GAR, accuracy and balanced accuracy at ``threshold``.

    ``small_sample_floor`` controls a warning when either class has fewer trials.
    """
    g = _as_array(genuine_scores)
    i = _as_array(impostor_scores)
    n_g = int(g.size)
    n_i = int(i.size)

    far_v = far(i, threshold)
    frr_v = frr(g, threshold)
    gar_v = None if frr_v is None else 1.0 - frr_v

    accuracy: float | None
    balanced: float | None
    if n_g + n_i == 0:
        accuracy = None
    else:
        tp = int(np.count_nonzero(g >= threshold)) if n_g else 0
        tn = int(np.count_nonzero(i < threshold)) if n_i else 0
        accuracy = (tp + tn) / (n_g + n_i)

    if far_v is None or gar_v is None:
        balanced = None
    else:
        balanced = (gar_v + (1.0 - far_v)) / 2.0

    warnings: list[str] = []
    if n_g == 0 or n_i == 0:
        warnings.append(EMPTY_CLASS)
    if 0 < n_g < small_sample_floor or 0 < n_i < small_sample_floor:
        warnings.append("SMALL_SAMPLE")

    return RateReport(
        threshold=float(threshold),
        n_genuine=n_g,
        n_impostor=n_i,
        far=far_v,
        frr=frr_v,
        gar=gar_v,
        accuracy=accuracy,
        balanced_accuracy=balanced,
        warnings=tuple(warnings),
    )
