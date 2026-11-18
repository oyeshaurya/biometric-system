"""Pure metric functions: FAR, FRR, GAR, accuracy, Wilson intervals, EER, sweep.

This package has no I/O and no imports from ``db`` or ``api`` (ARCHITECTURE.md rule).
Every function is deterministic for identical inputs (NFR-03).
"""

from biometric_lab.core.metrics.eer import EerResult, equal_error_rate
from biometric_lab.core.metrics.rates import RateReport, rate_report
from biometric_lab.core.metrics.sweep import SweepResult, threshold_sweep
from biometric_lab.core.metrics.wilson import rule_of_three_upper, wilson_interval

__all__ = [
    "EerResult",
    "equal_error_rate",
    "RateReport",
    "rate_report",
    "SweepResult",
    "threshold_sweep",
    "rule_of_three_upper",
    "wilson_interval",
]
