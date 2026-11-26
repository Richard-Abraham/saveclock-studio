"""Energy curve, per-bar energy levels and sections (pure functions over lists)."""

from dataclasses import dataclass
from itertools import pairwise

CURVE_HZ = 10
THRESHOLDS = (0.25, 0.5, 0.75)
LEVELS = ("e1", "e2", "e3", "e4")
LABELS = {"e1": "quiet", "e2": "low", "e3": "driving", "e4": "peak"}
RISE_TO_E4 = 0.35


@dataclass(frozen=True)
class Section:
    id: str
    start_s: float
    end_s: float
    label: str
    energy: str


def _percentile(sorted_values: list[float], q: float) -> float:
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def energy_curve(rms_db: list[float]) -> list[float]:
    """10 Hz curve normalised by the 5th and 95th percentile to [0, 1]."""
    if not rms_db:
        return []
    ordered = sorted(rms_db)
    lo, hi = _percentile(ordered, 0.05), _percentile(ordered, 0.95)
    if hi - lo < 1e-9:  # noqa: PLR2004
        return [0.5] * len(rms_db)
    return [min(1.0, max(0.0, (v - lo) / (hi - lo))) for v in rms_db]


def bar_energy(curve: list[float], downbeats_s: list[float]) -> list[float]:
    """Mean energy of every bar between two consecutive downbeats."""
    out: list[float] = []
    for a, b in pairwise(downbeats_s):
        i, j = int(a * CURVE_HZ), max(int(b * CURVE_HZ), int(a * CURVE_HZ) + 1)
        window = curve[i:j]
        out.append(sum(window) / len(window) if window else 0.0)
    return out


def levels(bars: list[float]) -> list[str]:
    out: list[str] = []
    for i, e in enumerate(bars):
        level = sum(e >= t for t in THRESHOLDS)  # 0..3
        rose = i > 0 and e - bars[i - 1] >= RISE_TO_E4
        out.append("e4" if level >= 2 and rose else LEVELS[level])  # noqa: PLR2004
    return out


@dataclass
class _Run:
    level: str
    first: int
    count: int


def sections(bar_levels: list[str], downbeats_s: list[float], min_bars: int = 2) -> list[Section]:
    """Maximal equal-level runs; runs shorter than `min_bars` merge into the previous one.

    Every start and end is a downbeat by construction (bar i spans downbeats i and i + 1).
    """
    runs: list[_Run] = []
    for i, level in enumerate(bar_levels):
        if runs and runs[-1].level == level:
            runs[-1].count += 1
        else:
            runs.append(_Run(level, i, 1))
    merged: list[_Run] = []
    for run in runs:
        if merged and (run.count < min_bars or merged[-1].level == run.level):
            merged[-1].count += run.count
        else:
            merged.append(run)
    if len(merged) > 1 and merged[0].count < min_bars:  # a short first run joins the next one
        merged[1].first, merged[1].count = merged[0].first, merged[0].count + merged[1].count
        merged.pop(0)
    return [
        Section(
            id=f"s{n}",
            start_s=downbeats_s[r.first],
            end_s=downbeats_s[r.first + r.count],
            label=LABELS[r.level],
            energy=r.level,
        )
        for n, r in enumerate(merged, start=1)
    ]
