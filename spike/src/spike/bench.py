"""Timing helpers: ``/proc/stat`` steal, repeat-until-quiet, summary statistics."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import numpy as np

from spike.stats import mean, median, p95

T = TypeVar("T")
MAX_STEAL_PCT = 5.0


def cpu_times() -> tuple[int, int]:
    """(steal, total) jiffies from the aggregate ``cpu`` line of /proc/stat."""
    with open("/proc/stat", encoding="ascii") as fh:
        parts = [int(x) for x in fh.readline().split()[1:9]]
    return parts[7], sum(parts)


def steal_pct(before: tuple[int, int], after: tuple[int, int]) -> float:
    d_total = after[1] - before[1]
    return 0.0 if d_total <= 0 else 100.0 * (after[0] - before[0]) / d_total


def run_quiet[T](fn: Callable[[], T], retries: int = 3) -> tuple[T, float, int]:
    """Run ``fn``; discard and repeat while %steal over the run exceeds 5%.
    Returns (result, steal_pct, attempts)."""
    pct = 0.0
    for attempt in range(1, retries + 2):
        a = cpu_times()
        res = fn()
        pct = steal_pct(a, cpu_times())
        if pct <= MAX_STEAL_PCT:
            return res, pct, attempt
    return res, pct, retries + 1


def summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": len(values),
        "mean_s": mean(arr),
        "median_s": median(arr),
        "p95_s": p95(arr),
        "min_s": float(arr.min()),
        "max_s": float(arr.max()),
    }
