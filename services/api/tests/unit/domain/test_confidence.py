import itertools
import random

from saveclock.domain.confidence import (
    energy_grid,
    even_grid,
    low_confidence_ranges,
    score,
    signals,
)

PERIOD = 0.5  # 120 BPM


def regular(n: int = 65) -> list[float]:
    return [i * PERIOD for i in range(n)]


def downbeats_of(beats: list[float]) -> list[float]:
    return beats[::4]


def jittered(n: int = 65, amount: float = 0.3, seed: int = 7) -> list[float]:
    rng = random.Random(seed)  # noqa: S311 - a test fixture, not security
    t, out = 0.0, []
    for _ in range(n):
        out.append(t)
        t += PERIOD * (1 + rng.uniform(-amount, amount))
    return out


def test_a_regular_grid_on_audible_events_is_high() -> None:
    beats = regular()
    sig = signals(beats, downbeats_of(beats), 120.0, (3.0, 1.0), 1.0)
    result = score(sig)
    assert result.score >= 0.8
    assert result.band == "high"
    assert result.reasons == []


def test_a_jittery_grid_off_the_events_is_low_with_reasons() -> None:
    beats = jittered()
    sig = signals(beats, downbeats_of(beats), 120.0, (1.0, 1.0), 1.0)
    result = score(sig)
    assert result.score < 0.5
    assert result.band == "low"
    assert "irregular_beats" in result.reasons
    assert "beats_off_events" in result.reasons


def test_octave_ambiguity_is_flagged() -> None:
    beats = regular()
    ratios = {240.0: 0.2, 120.0: 1.0, 80.0: 0.2, 60.0: 0.2, 90.0: 0.6}  # onset tempo -> S3
    for onset_tempo, expected in ratios.items():
        sig = signals(beats, downbeats_of(beats), onset_tempo, (3.0, 1.0), 1.0)
        assert sig["s3"] == expected, onset_tempo
    assert signals(beats, downbeats_of(beats), None, (3.0, 1.0), 1.0)["s3"] == 0.5


def test_inconsistent_bars_lower_s5() -> None:
    beats = regular(33)
    sig = signals(beats, [0.0, 2.0, 4.0, 5.0, 7.0], 120.0, (3.0, 1.0), 1.0)  # 4, 4, 2, 4 beats
    assert sig["s5"] == 0.75
    assert signals(beats, [], 120.0, (3.0, 1.0), 1.0)["s5"] == 0.3


def test_band_edges_are_inclusive_at_the_lower_bound() -> None:
    def at(total: float) -> str:
        return score(
            {"s1": total, "s2": total, "s3": total, "s4": total, "s5": total, "s8": total}
        ).band

    assert at(0.5) == "medium"
    assert at(0.8) == "high"
    assert at(0.49) == "low"
    assert at(0.79) == "medium"


def test_degenerate_grids_do_not_crash() -> None:
    assert score(signals([], [], None, (0.0, 0.0), 0.0)).band == "low"
    assert signals([0.0], [0.0], 120.0, (0.0, 0.0), 1.0)["s1"] == 0.0


def test_low_confidence_ranges_find_the_wandering_window() -> None:
    beats = regular(17) + [8.0 + 0.5 * (i + 1) + (0.2 if i % 2 else -0.2) for i in range(16)]
    assert low_confidence_ranges(regular(65)) == []
    spans = low_confidence_ranges(beats)
    assert len(spans) == 1
    assert spans[0][0] >= 8.0 - 1e-9


def test_energy_grid_never_yields_a_shot_under_fifteen_frames() -> None:
    peaks = [0.0, 0.1, 0.2, 0.55, 0.6, 1.2, 1.7]
    grid = energy_grid(peaks)
    assert grid == [0.0, 0.55, 1.2, 1.7]
    gaps = [round((b - a) * 30) for a, b in itertools.pairwise(grid)]
    assert min(gaps) >= 15
    assert energy_grid([]) == []


def test_even_grid_spans_the_beats_at_the_median_interval() -> None:
    beats = [0.0, 0.5, 1.02, 1.5, 2.0, 2.52, 3.0]
    grid = even_grid(beats)
    assert len(grid) == 7
    assert abs(grid[1] - grid[0] - 0.5) < 1e-9
    assert even_grid([1.0]) == [1.0]
