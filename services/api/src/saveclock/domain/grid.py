"""The effective beat grid of a plan, built from the stored RAW beat map (never re-inferred).

Owner choices change the grid, not the model's output: the half/double step, the typed tempo, the
even grid and the energy grid. Pure Python lists, times rounded to 6 decimals like the plan's.
"""

import statistics
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from saveclock.domain.beat_grid import (
    BEATS_PER_BAR,
    MIN_BEATS,
    apply_octave,
    clamp_octave,
    fold_downbeats,
    median_bpm,
)

GridMode = Literal["detected", "energy", "even", "bpm"]
MAX_BEATS = 5000  # a typed tempo cannot make a grid of millions of beats


class GridError(ValueError):
    """The requested grid cannot be built from the stored beats (a reason string for the API)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class GridChoice:
    """What the owner chose; the plan's `beat_grid.source` and octave carry it between edits."""

    mode: GridMode = "detected"
    octave: int = 0
    bpm: float | None = None


@dataclass(frozen=True)
class GridView:
    beats_s: tuple[float, ...]
    downbeats_s: tuple[float, ...]
    bpm: float
    source: str
    fallback: str | None
    octave_total: int  # the plan's `tempo_octave_adjust`: the automatic fold plus the owner's step


def _r(values: list[float]) -> list[float]:
    return [round(v, 6) for v in values]


def beats_per_bar(
    downbeats: list[float] | tuple[float, ...], beats: list[float] | tuple[float, ...]
) -> int:
    """Median number of beats between consecutive downbeats; 4 when it cannot be read."""
    if len(downbeats) < MIN_BEATS or not beats:
        return BEATS_PER_BAR
    counts = [sum(1 for b in beats if a - 1e-6 <= b < d - 1e-6) for a, d in pairwise(downbeats)]
    counts = [c for c in counts if c > 0]
    return int(statistics.median(counts)) if counts else BEATS_PER_BAR


def even_grid_from_beats(beats: list[float]) -> list[float]:
    """The least-squares line `t_k = t_0 + k * T` through the beats (both `t_0` and `T` fitted).

    shortcut: fitted to the beats only (no onset alignment); upgrade if QM-025 shows it is worse
    than chance.
    """
    n = len(beats)
    if n < MIN_BEATS:
        raise GridError("not_enough_beats")
    mean_k, mean_t = (n - 1) / 2, statistics.fmean(beats)
    spread = sum((k - mean_k) ** 2 for k in range(n))
    period = sum((k - mean_k) * (t - mean_t) for k, t in enumerate(beats)) / spread
    offset = mean_t - period * mean_k
    return [offset + k * period for k in range(n)]


def grid_from_bpm(bpm: float, phase_s: float, duration_s: float) -> list[float]:
    """A grid at a typed tempo, starting at the first detected beat (`phase_s`)."""
    period = 60.0 / bpm
    count = int((duration_s - phase_s) / period) + 1
    if count < 1:
        raise GridError("not_enough_beats")
    if count > MAX_BEATS:
        raise GridError("bpm_out_of_range")
    return [phase_s + k * period for k in range(count)]


def _downbeats_for(beats: list[float], anchor_s: float, bpb: int) -> list[float]:
    """Every `bpb`-th beat, in phase with the beat nearest the detected downbeat `anchor_s`."""
    nearest = min(range(len(beats)), key=lambda i: abs(beats[i] - anchor_s))
    return beats[nearest % bpb :: bpb]


def effective_grid(
    raw_beats: list[float],
    raw_downbeats: list[float],
    *,
    choice: GridChoice,
    fallback_grid: list[float] | None,
    duration_s: float,
    model_name: str,
) -> GridView:
    """The grid for a choice; `fallback_grid` is the stored energy grid, or None."""
    clamped, auto = clamp_octave(raw_beats)
    bpb = beats_per_bar(raw_downbeats, raw_beats)
    anchor = raw_downbeats[0] if raw_downbeats else raw_beats[0]
    fallback: str | None = None
    if choice.mode == "detected":
        beats = apply_octave(clamped, choice.octave)
        downs, _ = fold_downbeats(raw_downbeats, beats)
        octave, source = auto + choice.octave, model_name
    elif choice.mode == "energy":
        if not fallback_grid:
            raise GridError("no_fallback_grid")
        beats = apply_octave(list(fallback_grid), choice.octave)
        downs = _downbeats_for(beats, anchor, bpb)
        octave, source, fallback = choice.octave, "energy_grid", "energy_grid"
    elif choice.mode == "even":
        beats = apply_octave(even_grid_from_beats(clamped), choice.octave)
        downs = _downbeats_for(beats, anchor, bpb)
        octave, source, fallback = choice.octave, "even_grid", "even_grid"
    else:
        if choice.bpm is None:
            raise GridError("bpm_missing")
        beats = grid_from_bpm(choice.bpm, clamped[0], duration_s)
        downs = _downbeats_for(beats, anchor, bpb)
        octave, source, fallback = 0, f"bpm:{choice.bpm:g}", "even_grid"
    if len(beats) < MIN_BEATS:
        raise GridError("not_enough_beats")
    bpm = choice.bpm if choice.mode == "bpm" and choice.bpm else (median_bpm(beats) or 0.0)
    return GridView(tuple(_r(beats)), tuple(_r(downs)), round(bpm, 6), source, fallback, octave)


def choice_from_plan(source: str, octave_total: int, auto_octave: int, bpm: float) -> GridChoice:
    """Read the owner's grid choice back from a stored plan's `beat_grid` (no extra column)."""
    if source == "energy_grid":
        return GridChoice("energy", octave_total)
    if source == "even_grid":
        return GridChoice("even", octave_total)
    if source.startswith("bpm:"):
        return GridChoice("bpm", 0, float(source.removeprefix("bpm:")) or bpm)
    return GridChoice("detected", octave_total - auto_octave)
