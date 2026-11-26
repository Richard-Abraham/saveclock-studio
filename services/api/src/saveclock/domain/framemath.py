"""The frame-index cut rule (DECISIONS 4, ARCHITECTURE 11.1).

``f_i = floor((t_i - t0) * fps + 0.5) - lead`` for ``i > 0``; ``f_0 = 0``. Never ``round()``
(banker's rounding), and never the sum of rounded durations (accumulates error).
"""

import itertools
import math
from collections.abc import Sequence

FPS = 30


def cut_frames(beat_times: Sequence[float], t0: float, fps: int = FPS, lead: int = 0) -> list[int]:
    """Output frame index of every beat boundary. Index 0 is the segment start (frame 0)."""
    out: list[int] = []
    for i, t in enumerate(beat_times):
        if i == 0:
            out.append(0)
        else:
            out.append(math.floor((t - t0) * fps + 0.5) - lead)
    return out


def shot_lengths(frames: Sequence[int]) -> list[int]:
    """Shot lengths are integer index differences, never summed rounded durations."""
    return [b - a for a, b in itertools.pairwise(frames)]
