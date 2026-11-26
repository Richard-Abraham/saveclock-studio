"""The default segment: the loudest window that starts on a downbeat (ARCH §11, ROADMAP T-2.3)."""

from dataclasses import dataclass

from saveclock.domain.framemath import FPS


class SegmentTooLong(ValueError):
    """The requested output is longer than the song (output length is capped at the song's)."""


@dataclass(frozen=True)
class Segment:
    start_s: float
    end_s: float
    total_frames: int


def select_segment(
    bar_energy: list[float], downbeats_s: list[float], duration_s: float, length_s: float
) -> Segment:
    """Downbeat start whose window [start, start + length) has the highest mean bar energy.

    Ties go to the earliest start. Bar i spans downbeats i and i + 1.
    """
    if length_s > duration_s:
        msg = "segment is longer than the song"
        raise SegmentTooLong(msg)
    best_start, best_mean = 0.0, -1.0  # shortcut: no downbeat fits -> start at 0, upgrade never
    for start in downbeats_s[: len(bar_energy)]:
        if start + length_s > duration_s:
            break
        window = [
            e
            for e, d in zip(bar_energy, downbeats_s, strict=False)
            if start <= d < start + length_s
        ]
        mean = sum(window) / len(window) if window else 0.0
        if mean > best_mean:
            best_start, best_mean = start, mean
    return Segment(best_start, best_start + length_s, round(length_s * FPS))
