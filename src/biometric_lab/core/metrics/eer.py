"""Equal Error Rate (SYSTEM_DESIGN.md section 8.4).

FAR(t) is non-increasing and FRR(t) is non-decreasing in t, so d(t) = FRR(t) - FAR(t)
is non-decreasing. The EER is where FAR and FRR cross. We report both the discrete value
(at the first candidate threshold where d >= 0) and a linearly interpolated value.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EPS = 1e-9
EMPTY_CLASS = "EMPTY_CLASS"
CLASSES_NOT_ORDERED = "CLASSES_NOT_ORDERED"


@dataclass(frozen=True)
class EerResult:
    """Discrete and interpolated EER with the thresholds at which they occur."""

    discrete_value: float | None
    discrete_threshold: float | None
    interpolated_value: float | None
    interpolated_threshold: float | None
    reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "discrete": None
            if self.discrete_value is None
            else {"value": self.discrete_value, "threshold": self.discrete_threshold},
            "interpolated": None
            if self.interpolated_value is None
            else {
                "value": self.interpolated_value,
                "threshold": self.interpolated_threshold,
            },
            "reason": self.reason,
        }


def _far_frr_at(
    candidates: np.ndarray, genuine_sorted: np.ndarray, impostor_sorted: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised FAR(t) and FRR(t) over sorted candidate thresholds."""
    n_g = genuine_sorted.size
    n_i = impostor_sorted.size
    # count(impostor >= t) = n_i - searchsorted(impostor, t, 'left')
    far = (n_i - np.searchsorted(impostor_sorted, candidates, side="left")) / n_i
    # count(genuine < t) = searchsorted(genuine, t, 'left')
    frr = np.searchsorted(genuine_sorted, candidates, side="left") / n_g
    return far, frr


def equal_error_rate(genuine_scores: object, impostor_scores: object) -> EerResult:
    """Compute the discrete and interpolated EER.

    Returns an :class:`EerResult`. ``reason`` is set when a result is not available.
    """
    g = np.asarray(genuine_scores, dtype=np.float64).ravel()
    i = np.asarray(impostor_scores, dtype=np.float64).ravel()
    if g.size == 0 or i.size == 0:
        return EerResult(None, None, None, None, reason=EMPTY_CLASS)

    g_sorted = np.sort(g)
    i_sorted = np.sort(i)

    uniq = np.unique(np.concatenate([g_sorted, i_sorted]))
    candidates = np.append(uniq, uniq[-1] + EPS)

    far, frr = _far_frr_at(candidates, g_sorted, i_sorted)
    d = frr - far  # non-decreasing

    ge = np.nonzero(d >= 0.0)[0]
    if ge.size == 0:
        # Should not happen: at the sentinel FRR=1, FAR=0, so d=1 >= 0.
        k = len(candidates) - 1
    else:
        k = int(ge[0])

    discrete_value = float((far[k] + frr[k]) / 2.0)
    discrete_threshold = float(candidates[k])

    if k == 0:
        # d >= 0 already at the lowest candidate: classes do not overlap as expected.
        return EerResult(
            discrete_value,
            discrete_threshold,
            discrete_value,
            discrete_threshold,
            reason=CLASSES_NOT_ORDERED,
        )

    a = d[k - 1]  # < 0
    b = d[k]  # >= 0
    if b == a:
        interp_value = discrete_value
        interp_threshold = discrete_threshold
    else:
        w = -a / (b - a)
        interp_value = float(far[k - 1] + w * (far[k] - far[k - 1]))
        interp_threshold = float(candidates[k - 1] + w * (candidates[k] - candidates[k - 1]))

    return EerResult(
        discrete_value,
        discrete_threshold,
        interp_value,
        interp_threshold,
    )
