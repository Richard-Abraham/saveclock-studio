"""Frame sampling counts and the vector arithmetic of ranking (pure, plain Python floats)."""

import math
from collections.abc import Sequence

from saveclock.domain.windows import Window

FRAMES_PER_CLIP = 8


def sample_count(window: Window, n: int = FRAMES_PER_CLIP) -> int:
    """One frame per second of the window, at most `n`, at least one."""
    return max(1, min(n, math.floor(window.len_s)))


def norm(v: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def normalize(v: Sequence[float]) -> list[float]:
    n = norm(v)
    return [x / n for x in v] if n > 0 else [0.0] * len(v)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """0.0 when either vector is all zeros."""
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


def mean_vector(vectors: Sequence[Sequence[float]]) -> tuple[float, ...]:
    return tuple(sum(col) / len(vectors) for col in zip(*vectors, strict=True))


def frame_scores(images: Sequence[Sequence[float]], text: Sequence[float]) -> list[float]:
    """Cosine similarity of every frame embedding with the keyword's text embedding."""
    return [cosine(img, text) for img in images]


def clip_score(scores: Sequence[float]) -> float:
    """The score of a clip is the mean over its frames."""
    return sum(scores) / len(scores)
