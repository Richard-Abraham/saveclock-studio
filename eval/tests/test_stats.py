from __future__ import annotations

import numpy as np
import pytest

from saveclock_eval.stats import bootstrap_ci, mean, median, p95, percentiles


def test_summary_and_ci() -> None:
    v = np.arange(1.0, 101.0)
    assert mean(v) == 50.5 and median(v) == 50.5
    assert p95(v) == 95.05  # linear interpolation: 1 + 0.95 * 99
    lo, hi = bootstrap_ci(v)
    assert lo < 50.5 < hi
    assert bootstrap_ci(v) == (lo, hi)  # fixed seed -> deterministic


def test_percentiles_of_a_short_list() -> None:
    got = percentiles([1.0, 2.0, 9.0])
    assert (got["p50"], got["max"]) == (2.0, 9.0)
    assert got["p95"] == pytest.approx(8.3)  # 2 + 0.9 * 7
