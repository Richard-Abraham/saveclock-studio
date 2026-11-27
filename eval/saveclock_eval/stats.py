"""Summary statistics. Percentiles use linear interpolation (numpy default). Ported from the spike."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


def mean(values: FloatArray) -> float:
    return float(np.mean(values))


def median(values: FloatArray) -> float:
    return float(np.median(values))


def p95(values: FloatArray) -> float:
    """95th percentile by linear interpolation between order statistics."""
    return float(np.percentile(values, 95, method="linear"))


def bootstrap_ci(
    values: FloatArray, resamples: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean: `resamples` draws with replacement, fixed seed."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(resamples, len(values)))
    means = values[idx].mean(axis=1)
    lo, hi = np.percentile(means, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(lo), float(hi)


def percentiles(values: list[float]) -> dict[str, float]:
    """p50, p95 and max of a non-empty list (the timing rows)."""
    arr = np.asarray(values, dtype=np.float64)
    return {"p50": median(arr), "p95": p95(arr), "max": float(arr.max())}
