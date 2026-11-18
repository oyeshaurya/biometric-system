"""Hand-computed rate checks (SYSTEM_DESIGN.md section 9.1).

G = {0.9, 0.8, 0.4}, I = {0.1, 0.3, 0.5}. Decision rule: accept if score >= t.
"""

from __future__ import annotations

import pytest

from biometric_lab.core.metrics.rates import far, frr, gar, rate_report

G = [0.9, 0.8, 0.4]
I = [0.1, 0.3, 0.5]


def test_rates_at_0_6():
    assert frr(G, 0.6) == pytest.approx(1 / 3)  # only 0.4 < 0.6
    assert far(I, 0.6) == pytest.approx(0.0)  # none >= 0.6


def test_rates_at_0_45():
    assert frr(G, 0.45) == pytest.approx(1 / 3)  # 0.4 < 0.45
    assert far(I, 0.45) == pytest.approx(1 / 3)  # 0.5 >= 0.45


def test_rates_at_boundary_0_5():
    # 0.5 >= 0.5 is accepted (impostor false accept); 0.4 < 0.5 is rejected (genuine).
    assert frr(G, 0.5) == pytest.approx(1 / 3)
    assert far(I, 0.5) == pytest.approx(1 / 3)


def test_gar_is_one_minus_frr():
    assert gar(G, 0.5) == pytest.approx(1 - 1 / 3)


def test_empty_impostor_returns_none():
    assert far([], 0.5) is None
    report = rate_report(G, [], 0.5)
    assert report.far is None
    assert "EMPTY_CLASS" in report.warnings


def test_empty_genuine_returns_none():
    assert frr([], 0.5) is None
    assert gar([], 0.5) is None


def test_report_accuracy_and_balanced():
    # At t=0.5: TP=count(g>=0.5)=2 (0.9,0.8), TN=count(i<0.5)=2 (0.1,0.3).
    report = rate_report(G, I, 0.5)
    assert report.accuracy == pytest.approx((2 + 2) / 6)
    # balanced = (GAR + (1 - FAR)) / 2 = ((2/3) + (1 - 1/3)) / 2 = 2/3
    assert report.balanced_accuracy == pytest.approx(2 / 3)
    assert report.n_genuine == 3
    assert report.n_impostor == 3


def test_small_sample_warning():
    report = rate_report(G, I, 0.5)
    assert "SMALL_SAMPLE" in report.warnings
