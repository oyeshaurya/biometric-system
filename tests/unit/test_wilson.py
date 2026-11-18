"""Wilson interval and rule of three (SYSTEM_DESIGN.md section 9.1)."""

from __future__ import annotations

import pytest

from biometric_lab.core.metrics.wilson import rule_of_three_upper, wilson_interval


def test_wilson_5_of_10():
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)


def test_wilson_zero_of_100():
    low, high = wilson_interval(0, 100)
    assert low == pytest.approx(0.0)
    assert high == pytest.approx(0.0370, abs=1e-3)


def test_wilson_zero_n_returns_none():
    assert wilson_interval(0, 0) is None


def test_wilson_rejects_out_of_range():
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_rule_of_three():
    assert rule_of_three_upper(200) == pytest.approx(0.015)
    assert rule_of_three_upper(0) is None
