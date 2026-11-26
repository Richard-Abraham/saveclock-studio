"""Beat-grid confidence (QUALITY §6.1/6.2) and the fallback grids (ladder steps 2 and 3).

shortcut: hand-set weights (P4-10), S6 (model activation) and S7 (eval-only) are omitted;
upgrade to the fitted model when a golden set exists (QM-022 to QM-024).
"""

import statistics
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise

from saveclock.domain.framemath import FPS

WINDOW = 16  # beats per S1/S2 window
IBI_TOL = 0.08
HIGH, MEDIUM = 0.80, 0.50
REASON_BELOW = 0.6
MIN_SHOT_FRAMES = 15
# the weights sum to 1; the keys are the signal names
WEIGHTS = {"s1": 0.35, "s2": 0.20, "s3": 0.15, "s4": 0.15, "s5": 0.10, "s8": 0.05}
REASONS = {
    "s1": "irregular_beats",
    "s2": "unstable_tempo",
    "s3": "octave_ambiguous",
    "s4": "beats_off_events",
    "s5": "inconsistent_bars",
    "s8": "audio_condition",
}
AMBIGUOUS_RATIOS = (2.0, 0.5, 1.5, 2.0 / 3.0)


@dataclass(frozen=True)
class Confidence:
    score: float
    band: str
    reasons: list[str]


def _intervals(beats: list[float]) -> list[float]:
    return [b - a for a, b in pairwise(beats)]


def _windows(ibis: list[float]) -> list[list[float]]:
    return [ibis[i : i + WINDOW] for i in range(0, max(len(ibis), 1), WINDOW)] if ibis else []


def _regular(window: list[float]) -> float:
    med = statistics.median(window)
    return sum(abs(x - med) <= IBI_TOL * med for x in window) / len(window)


def signals(
    beats: list[float],
    downbeats: list[float],
    onset_env_tempo: float | None,
    onset_at_beats: tuple[float, float],
    audio_condition: float,
) -> dict[str, float]:
    """S1 IBI regularity, S2 tempo stability, S3 octave ambiguity, S4 beat salience,
    S5 bar consistency, S8 audio condition; every value is in [0, 1], 1 = trustworthy."""
    ibis = _intervals(beats)
    wins = _windows(ibis)
    s1 = sum(_regular(w) for w in wins) / len(wins) if wins else 0.0
    if wins:
        cvs = [statistics.pstdev(w) / statistics.median(w) for w in wins]
        s2 = max(0.0, 1.0 - 5.0 * sum(cvs) / len(cvs))
    else:
        s2 = 0.0
    bpm = 60.0 / statistics.median(ibis) if ibis else 0.0
    if onset_env_tempo is None or bpm <= 0:
        s3 = 0.5
    else:
        ratio = bpm / onset_env_tempo
        if abs(ratio - 1.0) <= 0.05:  # noqa: PLR2004
            s3 = 1.0
        elif any(abs(ratio - r) <= 0.05 * r for r in AMBIGUOUS_RATIOS):
            s3 = 0.2
        else:
            s3 = 0.6
    at_beats, at_mid = onset_at_beats
    if at_mid > 0:
        s4 = max(0.0, min(1.0, (at_beats / at_mid - 1.0) / 2.0))
    else:
        s4 = 1.0 if at_beats > 0 else 0.0
    per_bar = [sum(a <= b < c for b in beats) for a, c in pairwise(downbeats)]
    s5 = Counter(per_bar).most_common(1)[0][1] / len(per_bar) if per_bar else 0.3
    return {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5, "s8": audio_condition}


def band_of(total: float) -> str:
    return "high" if total >= HIGH else "medium" if total >= MEDIUM else "low"


def score(sig: dict[str, float]) -> Confidence:
    total = round(sum(WEIGHTS[k] * sig[k] for k in WEIGHTS), 4)
    return Confidence(total, band_of(total), [REASONS[k] for k in WEIGHTS if sig[k] < REASON_BELOW])


def low_confidence_ranges(beats: list[float]) -> list[tuple[float, float]]:
    """Merged [start_s, end_s] spans of 16-beat windows whose regularity (S1) is below 0.6."""
    out: list[tuple[float, float]] = []
    for i in range(0, max(len(beats) - 1, 0), WINDOW):
        chunk = beats[i : i + WINDOW + 1]
        ibis = _intervals(chunk)
        if len(ibis) >= 2 and _regular(ibis) < REASON_BELOW:  # noqa: PLR2004
            if out and out[-1][1] >= chunk[0]:
                out[-1] = (out[-1][0], chunk[-1])
            else:
                out.append((chunk[0], chunk[-1]))
    return out


def energy_grid(onset_peaks_s: list[float], min_frames: int = MIN_SHOT_FRAMES) -> list[float]:
    """Ladder step 3: cut on strong energy peaks, never closer than `min_frames` at 30 fps."""
    gap = min_frames / FPS
    out: list[float] = []
    for t in sorted(onset_peaks_s):
        if not out or t - out[-1] >= gap - 1e-9:
            out.append(t)
    return out


def even_grid(beats: list[float]) -> list[float]:
    """Ladder step 2: a constant-tempo grid at the median interval.

    shortcut: the phase is the median offset of the model's beats, not an onset-aligned global
    fit; upgrade if a track shows a visible phase error.
    """
    ibis = _intervals(beats)
    if not ibis:
        return list(beats)
    period = statistics.median(ibis)
    phase = statistics.median(b - i * period for i, b in enumerate(beats))
    count = int((beats[-1] - phase) / period + 0.5) + 1
    return [phase + i * period for i in range(count)]
