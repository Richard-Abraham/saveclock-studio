"""The cut-free window of a clip: the longest stretch between two internal hard cuts."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from saveclock.domain.framemath import FPS
from saveclock.domain.stock_rules import MAX_WINDOW_S, MIN_WINDOW_S

MARGIN_S = 0.2  # a detected cut is a frame or two off: stay clear of both ends
EPS = 1e-6


@dataclass(frozen=True)
class Window:
    start_s: float
    len_s: float

    @property
    def frames(self) -> int:
        return math.floor(self.len_s * FPS + EPS)


def best_window(
    cut_times_s: Sequence[float],
    duration_s: float,
    *,
    max_len: float = MAX_WINDOW_S,
    min_len: float = MIN_WINDOW_S,
    margin_s: float = MARGIN_S,
) -> Window | None:
    """The longest interval between consecutive cuts (0 and the end included), shrunk by the
    margin at both ends and capped at `max_len`. Ties go to the earliest; None when what is left
    is shorter than `min_len`. The length is a whole number of frames (the mezzanine's -t)."""
    points = [0.0, *sorted(c for c in cut_times_s if 0.0 < c < duration_s), duration_s]
    start, end = max(pairwise(points), key=lambda p: p[1] - p[0])  # max keeps the first of a tie
    usable = min(end - start - 2 * margin_s, max_len)
    frames = math.floor(usable * FPS + EPS)
    if frames / FPS < min_len - EPS:
        return None
    return Window(round(start + margin_s, 3), round(frames / FPS, 6))
