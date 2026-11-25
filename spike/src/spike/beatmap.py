"""Beat-grid post-processing (pure functions)."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


def median_bpm(beats: FloatArray) -> float | None:
    """Median-interval tempo in BPM, or None with fewer than 2 beats."""
    if len(beats) < 2:
        return None
    return float(60.0 / np.median(np.diff(beats)))


def clamp_octave(beats: FloatArray, lo: float = 70.0, hi: float = 180.0) -> FloatArray:
    """Fold the beat grid into [lo, hi] BPM by halving (drop every 2nd beat) or doubling.

    Doubling inserts the midpoint between each pair of consecutive beats (and one half-interval
    after the last beat is NOT added, so the span is unchanged). Repeats until in range.
    """
    out = np.asarray(beats, dtype=np.float64)
    for _ in range(8):
        bpm = median_bpm(out)
        if bpm is None or lo <= bpm <= hi:
            return out
        if bpm > hi:
            out = out[::2]
        else:
            mids = (out[:-1] + out[1:]) / 2.0
            merged = np.empty(len(out) + len(mids), dtype=np.float64)
            merged[0::2] = out
            merged[1::2] = mids
            out = merged
    return out
