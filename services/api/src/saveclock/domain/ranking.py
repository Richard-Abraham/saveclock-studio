"""Ranking of vetted clips: reproducible order, the top-K cut, the near-duplicate warning."""

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from saveclock.domain.sampling import cosine
from saveclock.domain.windows import Window

TOPK_FACTOR = 1.3
NEAR_DUPLICATE = 0.9


@dataclass(frozen=True)
class RankedClip:
    provider: str
    provider_id: str
    query: str
    score: float
    window: Window
    mean_embedding: tuple[float, ...] = ()


def _tie_break(seed: int | str, clip: RankedClip) -> str:
    return hashlib.sha256(f"{seed}:{clip.provider}:{clip.provider_id}".encode()).hexdigest()


def rank(scored: Sequence[RankedClip], *, seed: int | str) -> list[RankedClip]:
    """Best score first; equal scores in a seeded hash order, so a rerun gives the same list.
    A clip found by two keywords appears once, with its better score."""
    best: dict[tuple[str, str], RankedClip] = {}
    for clip in scored:
        key = (clip.provider, clip.provider_id)
        if key not in best or clip.score > best[key].score:
            best[key] = clip
    return sorted(best.values(), key=lambda c: (-c.score, _tie_break(seed, c)))


def top_k_count(cuts: int, factor: float = TOPK_FACTOR) -> int:
    """K = ceil(factor x cuts); the rounding guards against 26.000000000000004."""
    return math.ceil(round(factor * cuts, 9))


def top_k(ranked: Sequence[RankedClip], cuts: int, factor: float = TOPK_FACTOR) -> list[RankedClip]:
    return list(ranked[: top_k_count(cuts, factor)])


def near_duplicates(
    ranked: Sequence[RankedClip], threshold: float = NEAR_DUPLICATE
) -> list[tuple[str, str]]:
    """Provider ids of adjacent clips whose mean embeddings are more similar than `threshold`."""
    return [
        (a.provider_id, b.provider_id)
        for a, b in pairwise(ranked)
        if cosine(a.mean_embedding, b.mean_embedding) > threshold
    ]


def diversity(top: Sequence[RankedClip]) -> int:
    """How many different keywords the chosen clips came from."""
    return len({c.query for c in top})
