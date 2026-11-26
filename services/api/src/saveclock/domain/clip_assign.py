"""Choose a clip for every slot (QUALITY §10.3 "Variety"): the best score not used yet, the keyword
rotating only at phrase boundaries, never the same clip twice in a row, a locked clip kept at its
boundary, a long slot split when no clip is long enough. Pure and deterministic (a seeded hash
breaks score ties)."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, replace

from saveclock.domain.edit_plan import Attribution
from saveclock.domain.rules import cut_rules_v1 as rules


class LockConflict(Exception):
    """A locked clip cannot stay where it is (ARCH §5 invariant 7)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class NoUsableClips(Exception):
    """No clip in the pool can fill a slot, even after splitting it."""


@dataclass(frozen=True)
class Slot:
    index: int
    start_frame: int
    end_frame: int
    beat_index: int
    kind: str
    t_s: float
    section_id: str
    label: str

    @property
    def length(self) -> int:
        return self.end_frame - self.start_frame


@dataclass(frozen=True)
class BeatPoint:
    """A grid beat inside the segment: where a slot may be split."""

    index: int
    t_s: float
    frame: int
    kind: str
    section_id: str
    label: str


@dataclass(frozen=True)
class PoolClip:
    provider: str
    provider_id: str
    query: str
    score: float
    mezzanine_key: str
    mezzanine_frames: int
    attribution: Attribution

    @property
    def key(self) -> tuple[str, str]:
        return (self.provider, self.provider_id)


@dataclass(frozen=True)
class LockedCut:
    """A cut the owner locked: its clip stays at the beat `t_s`."""

    t_s: float
    clip: PoolClip
    in_frame: int


@dataclass(frozen=True)
class AssignedCut:
    slot: Slot
    clip: PoolClip
    in_frame: int
    locked: bool


@dataclass(frozen=True)
class Assignment:
    cuts: list[AssignedCut]
    pool_exhausted: bool
    split_slots: int


def _tie(seed: int, clip: PoolClip) -> str:
    return hashlib.sha256(f"{seed}:{clip.provider}:{clip.provider_id}".encode()).hexdigest()


def matches(query: str, keyword: str) -> bool:
    """A found clip's query is its keyword or a broadened tail of it (`broaden`)."""
    return query == keyword or keyword.endswith(" " + query)


def rotation(keywords: Sequence[str], slot: Slot, bpb: int) -> str | None:
    """The keyword preferred for this slot: it changes only when a phrase ends."""
    if not keywords:
        return None
    phrase = (slot.beat_index // max(1, bpb)) // rules.PHRASE_BARS[slot.label]
    return keywords[phrase % len(keywords)]


def _best(options: Sequence[PoolClip], preferred: str | None, seed: int) -> PoolClip:
    return min(
        options,
        key=lambda c: (
            not (preferred is not None and matches(c.query, preferred)),
            -c.score,
            _tie(seed, c),
        ),
    )


def _split(slot: Slot, beats: Sequence[BeatPoint]) -> tuple[Slot, Slot] | None:
    """Cut the slot at the grid beat nearest its middle when both halves stay long enough."""
    lo, hi = slot.start_frame + rules.MIN_SHOT_FRAMES, slot.end_frame - rules.MIN_SHOT_FRAMES
    inside = [b for b in beats if lo <= b.frame <= hi and b.index > slot.beat_index]
    if not inside:
        return None
    middle = (slot.start_frame + slot.end_frame) / 2
    point = min(inside, key=lambda b: (abs(b.frame - middle), b.frame))
    first = replace(slot, end_frame=point.frame)
    second = Slot(
        slot.index, point.frame, slot.end_frame, point.index, point.kind, point.t_s,
        point.section_id, point.label,
    )  # fmt: skip
    return first, second


def assign(
    slots: Sequence[Slot],
    pool: Sequence[PoolClip],
    keywords: Sequence[str],
    *,
    locked: Sequence[LockedCut] = (),
    seed: int,
    bpb: int = 4,
    beats: Sequence[BeatPoint] = (),
) -> Assignment:
    work = list(slots)
    locks = {round(lc.t_s, 6): lc for lc in locked}
    if not locks.keys() <= {round(s.t_s, 6) for s in work}:
        raise LockConflict("lock_boundary_missing")
    reserved = {lc.clip.key for lc in locks.values()}
    last_used: dict[tuple[str, str], int] = {}
    out: list[AssignedCut] = []
    exhausted, splits, i = False, 0, 0
    prev: tuple[str, str] | None = None
    while i < len(work):
        slot = work[i]
        lock = locks.get(round(slot.t_s, 6))
        if lock is not None:
            if lock.clip.mezzanine_frames < slot.length:
                raise LockConflict("lock_clip_too_short")
            in_frame = min(lock.in_frame, lock.clip.mezzanine_frames - slot.length)
            chosen, locked_flag = lock.clip, True
        else:
            locked_flag = False
            fit = [c for c in pool if c.key not in reserved and c.mezzanine_frames >= slot.length]
            if not fit:
                halves = _split(slot, beats) if len(work) < rules.MAX_SHOTS else None
                if halves is None:
                    raise NoUsableClips
                work[i : i + 1] = list(halves)
                splits += 1
                continue
            options = [
                c for c in fit if c.key != prev
            ] or fit  # adjacent only if it is all there is
            fresh = [c for c in options if c.key not in last_used]
            if fresh:
                chosen = _best(fresh, rotation(keywords, slot, bpb), seed)
            else:
                exhausted = True
                oldest = min(last_used[c.key] for c in options)
                chosen = _best(
                    [c for c in options if last_used[c.key] == oldest],
                    rotation(keywords, slot, bpb),
                    seed,
                )
            in_frame = 0  # the window is already cut-free: "first N usable seconds"
        last_used[chosen.key] = len(out)
        prev = chosen.key
        out.append(AssignedCut(slot, chosen, in_frame, locked_flag))
        i += 1
    renumbered = [replace(c, slot=replace(c.slot, index=n)) for n, c in enumerate(out)]
    return Assignment(renumbered, exhausted, splits)
