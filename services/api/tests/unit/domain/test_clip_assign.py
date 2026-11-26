import itertools
from dataclasses import replace

import pytest

from saveclock.domain.clip_assign import (
    BeatPoint,
    LockConflict,
    LockedCut,
    NoUsableClips,
    PoolClip,
    Slot,
    assign,
    matches,
    rotation,
)
from saveclock.domain.planner import layout_cuts
from tests.unit.domain.plan_support import one_section, pool, uniform_grid


def slots(n: int, length: int = 30, label: str = "e3") -> list[Slot]:
    return [
        Slot(i, i * length, (i + 1) * length, i * 2, "downbeat" if i % 2 == 0 else "beat",
             round(i * 0.9375, 6), "s1", label)
        for i in range(n)
    ]  # fmt: skip


def test_no_repeats_while_the_pool_is_large_enough() -> None:
    for n_clips, n_slots in itertools.product((10, 20, 40), (5, 10, 10)):
        got = assign(slots(n_slots), pool(n_clips), ["neon city"], seed=3)
        keys = [a.clip.key for a in got.cuts]
        if n_clips >= n_slots:
            assert len(set(keys)) == len(keys)
            assert not got.pool_exhausted


def test_adjacent_clips_differ_even_when_the_pool_is_exhausted() -> None:
    got = assign(slots(12), pool(3), ["neon city"], seed=1)
    keys = [a.clip.key for a in got.cuts]
    assert got.pool_exhausted
    assert all(a != b for a, b in itertools.pairwise(keys))


def test_a_single_clip_pool_repeats_the_only_clip_and_says_so() -> None:
    got = assign(slots(3), pool(1), ["neon city"], seed=1)
    assert got.pool_exhausted
    assert len({a.clip.key for a in got.cuts}) == 1


def test_pool_exhausted_only_when_the_pool_is_smaller_than_the_cut_count() -> None:
    assert not assign(slots(8), pool(8), [], seed=1).pool_exhausted
    assert assign(slots(9), pool(8), [], seed=1).pool_exhausted


def test_the_oldest_clip_is_reused_first() -> None:
    got = assign(slots(6), pool(3), [], seed=1)
    keys = [a.clip.provider_id for a in got.cuts]
    assert keys[3:] == keys[:3]


def test_a_clip_never_runs_past_its_mezzanine() -> None:
    mixed = pool(6, frames=100) + [replace(c, mezzanine_frames=40) for c in pool(6)[:0]]
    got = assign(slots(5, length=60), mixed, [], seed=1)
    assert all(a.in_frame + a.slot.length <= a.clip.mezzanine_frames for a in got.cuts)


def test_a_short_clip_is_skipped_for_a_long_slot() -> None:
    clips = [replace(c, mezzanine_frames=20) for c in pool(3)] + [pool(4)[3]]
    got = assign(slots(1, length=60), clips, [], seed=1)
    assert got.cuts[0].clip.provider_id == "c003"


def test_the_best_score_wins_and_a_tie_is_seeded() -> None:
    same = [replace(c, score=0.5) for c in pool(6)]
    a = assign(slots(1), same, [], seed=1).cuts[0].clip.provider_id
    b = assign(slots(1), same, [], seed=1).cuts[0].clip.provider_id
    c = assign(slots(1), same, [], seed=2).cuts[0].clip.provider_id
    assert a == b
    assert {a, c} <= {x.provider_id for x in same}
    best = assign(slots(1), pool(6), [], seed=1).cuts[0].clip.provider_id
    assert best == "c000"


def test_the_keyword_rotates_only_at_phrase_boundaries() -> None:
    queries = ("sea", "city")
    clips = pool(40, queries=queries)
    spots = [replace(s, beat_index=i * 4) for i, s in enumerate(slots(16))]  # a bar per slot
    got = assign(spots, clips, ["sea", "city"], seed=1, bpb=4)
    wanted = [rotation(["sea", "city"], s, 4) for s in spots]
    assert [a.clip.query for a in got.cuts] == wanted
    changes = [i for i in range(1, 16) if wanted[i] != wanted[i - 1]]
    assert changes == [4, 8, 12]  # e3: a phrase is 4 bars


def test_no_keywords_means_the_best_clip() -> None:
    assert rotation([], slots(1)[0], 4) is None


def test_a_query_matches_its_keyword_or_a_tail_of_it() -> None:
    assert matches("neon city", "neon city")
    assert matches("city", "neon city")
    assert not matches("neon", "neon city")


def lock(s: Slot, c: PoolClip, in_frame: int = 5) -> LockedCut:
    return LockedCut(s.t_s, c, in_frame)


def test_a_locked_clip_keeps_its_cut_and_is_not_used_elsewhere() -> None:
    spots, clips = slots(5), pool(10)
    keep = clips[7]
    got = assign(spots, clips, [], locked=[lock(spots[2], keep)], seed=1)
    assert got.cuts[2].clip.key == keep.key
    assert got.cuts[2].locked
    assert got.cuts[2].in_frame == 5
    assert [a.clip.key for a in got.cuts].count(keep.key) == 1


def test_a_vanished_boundary_raises_lock_conflict() -> None:
    spots, clips = slots(5), pool(10)
    gone = LockedCut(99.0, clips[0], 0)
    with pytest.raises(LockConflict) as err:
        assign(spots, clips, [], locked=[gone], seed=1)
    assert err.value.reason == "lock_boundary_missing"


def test_a_locked_clip_too_short_for_its_new_cut_is_a_conflict() -> None:
    spots = slots(3, length=90)
    short = replace(pool(2)[0], mezzanine_frames=50)
    with pytest.raises(LockConflict) as err:
        assign(spots, pool(5), [], locked=[lock(spots[1], short)], seed=1)
    assert err.value.reason == "lock_clip_too_short"


def test_a_locked_in_frame_is_clamped_into_the_clip() -> None:
    spots = slots(2, length=30)
    clip = replace(pool(1)[0], mezzanine_frames=40)
    got = assign(spots, pool(5), [], locked=[lock(spots[0], clip, in_frame=30)], seed=1)
    assert got.cuts[0].in_frame == 10


def test_a_slot_longer_than_every_clip_is_split_at_the_middle_beat() -> None:
    layout = layout_cuts(uniform_grid(128.0), one_section("e1"), 0.0, 900, density=-2)
    long_slot = layout.slots[0]
    clips = pool(30, frames=long_slot.length - 20)
    got = assign(layout.slots, clips, [], seed=1, bpb=layout.bpb, beats=layout.points)
    assert got.split_slots >= 1
    assert sum(a.slot.length for a in got.cuts) == 900
    assert [a.slot.index for a in got.cuts] == list(range(len(got.cuts)))
    first, second = got.cuts[0].slot, got.cuts[1].slot
    assert first.end_frame == second.start_frame
    middle = (long_slot.start_frame + long_slot.end_frame) / 2
    assert abs(first.end_frame - middle) <= 15


def test_a_slot_that_cannot_be_split_has_no_usable_clip() -> None:
    with pytest.raises(NoUsableClips):
        assign(slots(2, length=60), pool(4, frames=30), [], seed=1)


def test_splitting_stops_at_the_cut_cap() -> None:
    many = slots(60, length=20)
    points = [BeatPoint(i, i * 0.5, i * 15, "beat", "s1", "e3") for i in range(120)]
    with pytest.raises(NoUsableClips):
        assign(many, pool(70, frames=10), [], seed=1, beats=points)
