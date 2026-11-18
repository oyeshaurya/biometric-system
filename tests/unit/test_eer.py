"""EER checks (SYSTEM_DESIGN.md section 9.1), all hand-computed."""

from __future__ import annotations

import numpy as np
import pytest

from biometric_lab.core.metrics.eer import equal_error_rate


def test_example_a_overlapping():
    # G = {0.9, 0.8, 0.4}, I = {0.1, 0.3, 0.5}; crossing at t = 0.5, EER = 1/3.
    res = equal_error_rate([0.9, 0.8, 0.4], [0.1, 0.3, 0.5])
    assert res.discrete_value == pytest.approx(1 / 3)
    assert res.discrete_threshold == pytest.approx(0.5)


def test_example_b_separable():
    # Fully separable: EER = 0 at t = 0.8.
    res = equal_error_rate([0.9, 0.8], [0.1, 0.2])
    assert res.discrete_value == pytest.approx(0.0)
    assert res.discrete_threshold == pytest.approx(0.8)
    assert res.interpolated_value == pytest.approx(0.0)


def test_example_c_identical_distributions():
    # Identical: discrete EER = 0.5 at t = 0.9; interpolated EER = 0.5 at t = 0.7.
    res = equal_error_rate([0.1, 0.5, 0.9], [0.1, 0.5, 0.9])
    assert res.discrete_value == pytest.approx(0.5)
    assert res.interpolated_value == pytest.approx(0.5, abs=1e-9)
    assert res.interpolated_threshold == pytest.approx(0.7)


def test_empty_class():
    res = equal_error_rate([], [0.1, 0.2])
    assert res.discrete_value is None
    assert res.reason == "EMPTY_CLASS"


def test_symmetry_under_negation():
    # Negating scores and swapping labels gives the same EER value.
    g = [0.9, 0.8, 0.4]
    i = [0.1, 0.3, 0.5]
    a = equal_error_rate(g, i)
    b = equal_error_rate([-x for x in i], [-x for x in g])
    assert a.discrete_value == pytest.approx(b.discrete_value)


def test_monotonicity_property():
    # FAR non-increasing, FRR non-decreasing across thresholds (random but seeded).
    rng = np.random.default_rng(42)
    g = rng.normal(0.7, 0.1, size=200)
    i = rng.normal(0.1, 0.1, size=200)
    from biometric_lab.core.metrics.sweep import threshold_sweep

    sweep = threshold_sweep(g, i, max_points=0)  # full resolution
    far = np.asarray(sweep.far)
    frr = np.asarray(sweep.frr)
    assert np.all(np.diff(far) <= 1e-12)
    assert np.all(np.diff(frr) >= -1e-12)
