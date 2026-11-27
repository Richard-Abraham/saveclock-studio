"""Beat annotation files: one beat time (seconds) per line, optional 2nd column ``1`` = downbeat.

Ported from the spike (`spike/src/spike/annot.py`), unchanged in behaviour.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

BAR_TOLERANCE = 0.08  # relative bar-duration deviation from the median that raises a warning


class AnnotationError(ValueError):
    """The annotation is structurally invalid (not merely suspicious)."""


def write_beats(path: Path, times: FloatArray, downbeat_mask: npt.NDArray[np.bool_]) -> None:
    """Write beats; downbeats get a second column ``1``."""
    if len(times) != len(downbeat_mask):
        raise AnnotationError("times and downbeat_mask must have the same length")
    lines = [f"{t:.6f}\t1" if d else f"{t:.6f}" for t, d in zip(times, downbeat_mask, strict=True)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_beats(path: Path) -> tuple[FloatArray, npt.NDArray[np.bool_]]:
    """Read and validate a ``.beats`` file. Returns (times, downbeat_mask)."""
    times: list[float] = []
    down: list[bool] = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = raw.split()
        if not parts:
            continue
        if len(parts) > 2:
            raise AnnotationError(f"{path}:{n}: expected 1 or 2 columns, got {len(parts)}")
        try:
            times.append(float(parts[0]))
        except ValueError as exc:
            raise AnnotationError(f"{path}:{n}: bad time {parts[0]!r}") from exc
        if len(parts) == 2 and parts[1] != "1":
            raise AnnotationError(
                f"{path}:{n}: second column must be 1 (downbeat), got {parts[1]!r}"
            )
        down.append(len(parts) == 2)
    t = np.asarray(times, dtype=np.float64)
    mask = np.asarray(down, dtype=np.bool_)
    validate_beats(t)
    return t, mask


def validate_beats(
    times: FloatArray, downbeat_mask: npt.NDArray[np.bool_] | None = None
) -> list[str]:
    """Raise AnnotationError for hard errors; return warnings (bar length, tempo change)."""
    if not np.all(np.isfinite(times)):
        raise AnnotationError("non-finite beat time")
    if len(times) and times[0] < 0:
        raise AnnotationError(f"negative beat time {times[0]}")
    if len(times) > 1 and not np.all(np.diff(times) > 0):
        bad = int(np.flatnonzero(np.diff(times) <= 0)[0]) + 2
        raise AnnotationError(f"beat times not strictly increasing (beat {bad})")
    warnings: list[str] = []
    if downbeat_mask is not None and int(downbeat_mask.sum()) >= 3:
        idx = np.flatnonzero(downbeat_mask)
        counts = np.diff(idx)
        if np.any(counts != counts[0]):
            warnings.append(f"inconsistent beats per bar: {sorted(set(counts.tolist()))}")
        bars = np.diff(times[idx])
        dev = np.abs(bars / np.median(bars) - 1.0)
        if np.any(dev > BAR_TOLERANCE):
            warnings.append(
                f"possible tempo change: {int((dev > BAR_TOLERANCE).sum())} of {len(bars)} bars "
                f"deviate more than {BAR_TOLERANCE:.0%} from the median bar length"
            )
    return warnings
