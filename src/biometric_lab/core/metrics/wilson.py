"""Wilson score interval and the rule of three (SYSTEM_DESIGN.md section 8.3).

These describe a single proportion p = x / n. For correlated trials (several from one
participant) the interval is optimistic; a subject-level bootstrap is reported alongside
(see services, not here).
"""

from __future__ import annotations

import math

Z_95 = 1.959963984540054  # standard normal 97.5th percentile


def wilson_interval(x: int, n: int, z: float = Z_95) -> tuple[float, float] | None:
    """95% Wilson score interval for ``x`` successes in ``n`` trials.

    Returns ``(low, high)`` clamped to [0, 1], or ``None`` when ``n == 0``.

    Check value: ``wilson_interval(5, 10)`` is approximately (0.2366, 0.7634).
    """
    if n <= 0:
        return None
    if x < 0 or x > n:
        raise ValueError(f"x={x} out of range for n={n}")
    p = x / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denom
    low = max(0.0, centre - half)
    high = min(1.0, centre + half)
    return (low, high)


def rule_of_three_upper(n: int) -> float | None:
    """Approximate 95% upper bound on a rate with zero observed errors in ``n`` trials.

    Returns ~3/n, or ``None`` when ``n == 0``.
    """
    if n <= 0:
        return None
    return 3.0 / n
