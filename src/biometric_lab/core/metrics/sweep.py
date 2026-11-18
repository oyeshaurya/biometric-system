"""Threshold sweep (SYSTEM_DESIGN.md sections 8.4-8.5).

Computes FAR(t) and FRR(t) across all candidate thresholds for plotting, with the EER
attached. The full-resolution curve can be decimated for display; export keeps it full.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from biometric_lab.core.metrics.eer import EerResult, equal_error_rate


@dataclass(frozen=True)
class SweepResult:
    thresholds: list[float]
    far: list[float]
    frr: list[float]
    eer: EerResult
    n_genuine: int
    n_impostor: int
    reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "curve": {"thresholds": self.thresholds, "far": self.far, "frr": self.frr},
            "eer": self.eer.as_dict(),
            "n_genuine": self.n_genuine,
            "n_impostor": self.n_impostor,
            "reason": self.reason,
        }


def _decimate_indices(n: int, max_points: int) -> np.ndarray:
    """Uniformly sample at most ``max_points`` indices, always keeping first and last."""
    if max_points <= 0 or n <= max_points:
        return np.arange(n)
    idx = np.linspace(0, n - 1, max_points)
    idx = np.unique(np.round(idx).astype(int))
    idx[0] = 0
    idx[-1] = n - 1
    return idx


def threshold_sweep(
    genuine_scores: object,
    impostor_scores: object,
    *,
    max_points: int = 1000,
) -> SweepResult:
    """FAR(t) and FRR(t) over all candidate thresholds, decimated to ``max_points``."""
    g = np.asarray(genuine_scores, dtype=np.float64).ravel()
    i = np.asarray(impostor_scores, dtype=np.float64).ravel()
    n_g = int(g.size)
    n_i = int(i.size)

    if n_g == 0 or n_i == 0:
        return SweepResult([], [], [], equal_error_rate(g, i), n_g, n_i, reason="EMPTY_CLASS")

    g_sorted = np.sort(g)
    i_sorted = np.sort(i)
    uniq = np.unique(np.concatenate([g_sorted, i_sorted]))
    candidates = np.append(uniq, uniq[-1] + 1e-9)

    far = (n_i - np.searchsorted(i_sorted, candidates, side="left")) / n_i
    frr = np.searchsorted(g_sorted, candidates, side="left") / n_g

    keep = _decimate_indices(candidates.size, max_points)
    return SweepResult(
        thresholds=candidates[keep].tolist(),
        far=far[keep].tolist(),
        frr=frr[keep].tolist(),
        eer=equal_error_rate(g, i),
        n_genuine=n_g,
        n_impostor=n_i,
    )
