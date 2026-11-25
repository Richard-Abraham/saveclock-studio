import itertools
import math

import pytest

from spike.framemath import cut_frames, shot_lengths

BEAT = 60.0 / 128.0  # 0.46875 s = 14.0625 frames


def beats(n: int) -> list[float]:
    return [i * BEAT for i in range(n)]


def test_worked_example_128_bpm() -> None:
    f = cut_frames(beats(65), 0.0)
    assert f[:9] == [0, 14, 28, 42, 56, 70, 84, 98, 113]
    assert f[64] == 900
    lengths = shot_lengths(f)
    assert set(lengths) == {14, 15}
    assert sum(lengths) == 900


def test_wrong_way_drifts_four_frames() -> None:
    wrong = 0
    for _ in range(64):
        wrong += round(BEAT * 30)  # summed rounded durations (the bug the rule prevents)
    assert wrong == 896
    assert cut_frames(beats(65), 0.0)[64] - wrong == 4


def test_strictly_increasing_and_error_bound() -> None:
    for bpm in (100.0, 120.0, 128.0, 133.3, 174.0):
        t = [i * 60.0 / bpm for i in range(200)]
        f = cut_frames(t, 0.0)
        assert all(b > a for a, b in itertools.pairwise(f))
        assert max(abs(fi / 30 - ti) for fi, ti in zip(f, t, strict=True)) <= 1 / 60 + 1e-12


def test_half_rounds_up_not_bankers() -> None:
    # 0.5 frame and 2.5 frames: round() would give 0 and 2; the rule gives 1 and 3
    f = cut_frames([0.0, 0.5 / 30, 2.5 / 30 + 1e-9], 0.0)
    assert f[1] == math.floor(0.5 + 0.5) == 1
    assert f[2] == 3
    assert round(2.5) == 2  # python's banker's rounding, the thing we must not use


def test_f0_is_zero_and_lead_applies_for_i_gt_0() -> None:
    t = [10.0, 10.5, 11.0, 11.5]
    assert cut_frames(t, 10.0, lead=1) == [0, 14, 29, 44]
    assert cut_frames(t, 10.0, lead=0) == [0, 15, 30, 45]


def test_t0_offset_uses_relative_time() -> None:
    t = [3.0 + i * BEAT for i in range(65)]
    assert cut_frames(t, 3.0) == cut_frames(beats(65), 0.0)


def test_shot_lengths_are_index_differences() -> None:
    assert shot_lengths([0, 14, 28, 42]) == [14, 14, 14]
    assert shot_lengths([0]) == []


@pytest.mark.parametrize("n", [1, 2])
def test_degenerate(n: int) -> None:
    assert cut_frames(beats(n), 0.0)[0] == 0
