from __future__ import annotations

import numpy as np

from spike.stats import bootstrap_ci, mean, median, p95


def test_summary_and_ci() -> None:
    v = np.arange(1.0, 101.0)
    assert mean(v) == 50.5 and median(v) == 50.5
    assert p95(v) == 95.05  # linear interpolation: 1 + 0.95 * 99
    lo, hi = bootstrap_ci(v)
    assert lo < 50.5 < hi
    assert bootstrap_ci(v) == (lo, hi)  # fixed seed -> deterministic
