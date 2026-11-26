"""Beat-grid post-processing (pure Python lists; numbers equal the spike's numpy results)."""

import statistics
from itertools import pairwise

LO_BPM = 70.0
HI_BPM = 180.0
MAX_FOLDS = 8
MIN_BEATS = 2
DOWNBEAT_TOL_S = 0.001
BEATS_PER_BAR = 4


def median_bpm(beats: list[float]) -> float | None:
    """Median-interval tempo in BPM, or None with fewer than 2 beats."""
    if len(beats) < MIN_BEATS:
        return None
    return 60.0 / statistics.median(b - a for a, b in pairwise(beats))


def _halve(beats: list[float]) -> list[float]:
    return beats[::2]


def _double(beats: list[float]) -> list[float]:
    out: list[float] = []
    for a, b in pairwise(beats):
        out += [a, (a + b) / 2.0]
    return [*out, beats[-1]]  # the span is unchanged: no half interval after the last beat


def apply_octave(beats: list[float], octave: int) -> list[float]:
    """octave < 0 halves that many times, octave > 0 doubles (the owner's half/double)."""
    out = list(beats)
    for _ in range(abs(octave)):
        out = _halve(out) if octave < 0 else _double(out) if len(out) > 1 else out
    return out


def clamp_octave(
    beats: list[float], lo: float = LO_BPM, hi: float = HI_BPM
) -> tuple[list[float], int]:
    """Fold the grid into [lo, hi] BPM. Returns (folded beats, signed fold count)."""
    out, folds = list(beats), 0
    for _ in range(MAX_FOLDS):
        bpm = median_bpm(out)
        if bpm is None or lo <= bpm <= hi:
            break
        step = -1 if bpm > hi else 1
        out, folds = apply_octave(out, step), folds + step
    return out, folds


def fold_downbeats(raw_downbeats: list[float], kept_beats: list[float]) -> tuple[list[float], bool]:
    """Downbeats that coincide (1 ms) with a kept beat. Returns (downbeats, derived).

    With fewer than 2 survivors, every 4th beat from the first is used and `derived` is True.
    """
    kept = sorted(kept_beats)
    survivors = [d for d in raw_downbeats if any(abs(d - b) <= DOWNBEAT_TOL_S for b in kept)]
    if len(survivors) >= MIN_BEATS:
        return survivors, False
    return kept[::BEATS_PER_BAR], True
