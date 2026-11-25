import numpy as np

from spike.beatmap import clamp_octave, median_bpm


def bpm_of(b: np.ndarray) -> float:
    v = median_bpm(b)
    assert v is not None
    return v


def grid(bpm: float, n: int = 17) -> np.ndarray:
    return np.arange(n) * 60.0 / bpm


def test_in_range_unchanged() -> None:
    for bpm in (70.0, 100.0, 128.0, 180.0):
        b = grid(bpm)
        np.testing.assert_array_equal(clamp_octave(b), b)


def test_halves_above_180() -> None:
    b = grid(240.0, 17)
    out = clamp_octave(b)
    assert abs(bpm_of(out) - 120.0) < 1e-9
    np.testing.assert_allclose(out, b[::2])


def test_doubles_below_70_with_midpoints() -> None:
    b = grid(60.0, 5)  # 0,1,2,3,4 s
    out = clamp_octave(b)
    np.testing.assert_allclose(out, [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4])
    assert abs(bpm_of(out) - 120.0) < 1e-9


def test_repeated_folding() -> None:
    out = clamp_octave(grid(30.0, 5))  # 30 -> 60 -> 120
    assert 70 <= bpm_of(out) <= 180
    out2 = clamp_octave(grid(400.0, 33))  # 400 -> 200 -> 100
    assert 70 <= bpm_of(out2) <= 180


def test_degenerate_inputs() -> None:
    assert len(clamp_octave(np.array([1.0]))) == 1
    assert len(clamp_octave(np.array([]))) == 0
