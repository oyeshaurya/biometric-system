"""Threshold sweep checks (SYSTEM_DESIGN.md section 9.1)."""

from __future__ import annotations

import numpy as np

from biometric_lab.core.metrics.sweep import threshold_sweep


def test_candidates_include_all_scores_and_sentinel():
    g = [0.9, 0.8, 0.4]
    i = [0.1, 0.3, 0.5]
    res = threshold_sweep(g, i, max_points=0)
    thr = res.thresholds
    for s in set(g + i):
        assert any(abs(s - t) < 1e-12 for t in thr)
    # sentinel strictly above the max score
    assert thr[-1] > max(g + i)


def test_curve_is_monotone():
    g = [0.9, 0.8, 0.4]
    i = [0.1, 0.3, 0.5]
    res = threshold_sweep(g, i, max_points=0)
    far = np.asarray(res.far)
    frr = np.asarray(res.frr)
    assert np.all(np.diff(far) <= 1e-12)
    assert np.all(np.diff(frr) >= -1e-12)


def test_decimation_keeps_endpoints():
    rng = np.random.default_rng(7)
    g = rng.normal(0.7, 0.1, size=500)
    i = rng.normal(0.1, 0.1, size=500)
    full = threshold_sweep(g, i, max_points=0)
    small = threshold_sweep(g, i, max_points=50)
    assert len(small.thresholds) <= 50
    assert small.thresholds[0] == full.thresholds[0]
    assert small.thresholds[-1] == full.thresholds[-1]


def test_empty_class_sweep():
    res = threshold_sweep([], [0.1], max_points=0)
    assert res.reason == "EMPTY_CLASS"
    assert res.thresholds == []
