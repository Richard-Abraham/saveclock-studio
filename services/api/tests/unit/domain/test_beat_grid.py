import pytest

from saveclock.domain.beat_grid import (
    apply_octave,
    clamp_octave,
    fold_downbeats,
    median_bpm,
)


def bpm_of(b: list[float]) -> float:
    v = median_bpm(b)
    assert v is not None
    return v


def grid(bpm: float, n: int = 17) -> list[float]:
    return [i * 60.0 / bpm for i in range(n)]


@pytest.mark.parametrize("bpm", [70.0, 100.0, 128.0, 180.0])
def test_in_range_unchanged(bpm: float) -> None:
    b = grid(bpm)
    assert clamp_octave(b) == (b, 0)


def test_halves_above_180() -> None:
    b = grid(240.0, 17)
    out, folds = clamp_octave(b)  # 240 -> 120
    assert folds == -1
    assert out == b[::2]
    assert abs(bpm_of(out) - 120.0) < 1e-9


def test_doubles_below_70_with_midpoints() -> None:
    out, folds = clamp_octave(grid(60.0, 5))  # 50 BPM style: 0..4 s at 60 BPM -> 120
    assert folds == 1
    assert out == pytest.approx([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4])


def test_fifty_bpm_becomes_one_hundred() -> None:
    out, folds = clamp_octave(grid(50.0, 6))
    assert folds == 1
    assert bpm_of(out) == pytest.approx(100.0)


def test_repeated_folding() -> None:
    out, folds = clamp_octave(grid(30.0, 5))  # 30 -> 60 -> 120
    assert folds == 2
    assert bpm_of(out) == pytest.approx(120.0)
    out2, folds2 = clamp_octave(grid(400.0, 33))  # 400 -> 200 -> 100
    assert folds2 == -2
    assert bpm_of(out2) == pytest.approx(100.0)


def test_degenerate_inputs() -> None:
    assert clamp_octave([1.0]) == ([1.0], 0)
    assert clamp_octave([]) == ([], 0)
    assert median_bpm([2.0]) is None


@pytest.mark.parametrize("bpm", [20.0, 33.3, 45.0, 69.9, 180.1, 200.0, 255.5, 333.0, 640.0])
def test_result_is_always_in_range(bpm: float) -> None:
    out, _ = clamp_octave(grid(bpm, 65))
    assert 70.0 <= bpm_of(out) <= 180.0


def test_apply_octave_round_trips_the_fold() -> None:
    b = grid(60.0, 9)
    out, folds = clamp_octave(b)
    assert apply_octave(b, folds) == out
    assert apply_octave(b, 0) == b


def test_downbeats_survive_halving_when_on_even_indices() -> None:
    beats = grid(240.0, 17)
    raw = [beats[i] for i in range(0, 17, 4)]  # every 4th beat: even indices
    kept, _ = clamp_octave(beats)
    out, derived = fold_downbeats(raw, kept)
    assert out == raw
    assert not derived


def test_downbeats_on_odd_indices_trigger_the_fallback() -> None:
    beats = grid(240.0, 17)
    raw = [beats[i] for i in (1, 5, 9, 13)]  # all land on dropped beats
    kept, _ = clamp_octave(beats)
    out, derived = fold_downbeats(raw, kept)
    assert derived
    assert out == kept[::4]


def test_three_four_bars_after_halving_use_the_fallback() -> None:
    beats = grid(240.0, 25)
    raw = [beats[i] for i in range(0, 25, 3)]  # 3/4 downbeats; halving leaves 0, 6, 12, 18, 24
    kept, _ = clamp_octave(beats)
    out, derived = fold_downbeats(raw, kept)
    assert not derived  # 0, 6, 12, ... survive
    assert out == [beats[i] for i in range(0, 25, 6)]
    out2, derived2 = fold_downbeats([beats[3]], kept)  # one survivor is too few
    assert derived2
    assert out2 == kept[::4]
