import itertools
import random

import pytest

from saveclock.domain.grid import (
    GridChoice,
    GridError,
    GridView,
    beats_per_bar,
    choice_from_plan,
    effective_grid,
    even_grid_from_beats,
    grid_from_bpm,
)

RAW = [round(k * 0.5, 6) for k in range(80)]  # 120 BPM
RAW_DOWN = RAW[::4]
ENERGY = [round(0.1 + k * 0.4, 6) for k in range(100)]  # 150 BPM


def grid(choice: GridChoice, *, fallback: list[float] | None = None) -> GridView:
    return effective_grid(
        RAW, RAW_DOWN, choice=choice, fallback_grid=fallback, duration_s=40.0, model_name="m:1"
    )


def test_octave_minus_one_halves_zero_keeps_plus_one_doubles() -> None:
    assert grid(GridChoice("detected", -1)).beats_s == tuple(RAW[::2])
    assert grid(GridChoice("detected", 0)).beats_s == tuple(RAW)
    doubled = grid(GridChoice("detected", 1))
    assert doubled.beats_s[:5] == (0.0, 0.25, 0.5, 0.75, 1.0)
    assert grid(GridChoice("detected", 1)).bpm == pytest.approx(240.0)
    assert grid(GridChoice("detected", -1)).octave_total == -1


def test_downbeats_survive_halving_and_doubling() -> None:
    for octave in (-1, 0, 1):
        g = grid(GridChoice("detected", octave))
        assert set(g.downbeats_s) <= set(g.beats_s)
        assert g.downbeats_s[:3] == (0.0, 2.0, 4.0)


def test_the_automatic_fold_is_part_of_the_total() -> None:
    fast = [round(k * 0.25, 6) for k in range(200)]  # 240 BPM: folded once to 120
    g = effective_grid(
        fast, fast[::4], choice=GridChoice(), fallback_grid=None, duration_s=40.0, model_name="m"
    )
    assert g.octave_total == -1
    assert g.bpm == pytest.approx(120.0)


def test_even_grid_recovers_the_period_within_two_milliseconds() -> None:
    rng = random.Random(4)  # noqa: S311 - a seeded test fixture
    jittered = [k * 0.5 + rng.uniform(-0.02, 0.02) for k in range(100)]
    fitted = even_grid_from_beats(jittered)
    steps = {round(b - a, 6) for a, b in itertools.pairwise(fitted)}
    assert all(abs(s - 0.5) < 0.002 for s in steps)
    assert all(abs(f - k * 0.5) < 0.02 for k, f in enumerate(fitted))


def test_an_even_grid_needs_two_beats() -> None:
    with pytest.raises(GridError) as err:
        even_grid_from_beats([1.0])
    assert err.value.reason == "not_enough_beats"


def test_a_typed_bpm_grid_starts_at_the_first_beat() -> None:
    beats = grid_from_bpm(100.0, 1.0, 10.0)
    assert beats[0] == 1.0
    assert beats[1] - beats[0] == pytest.approx(0.6)
    g = grid(GridChoice("bpm", 0, 100.0))
    assert g.source == "bpm:100"
    assert g.bpm == 100.0
    assert g.fallback == "even_grid"
    assert g.beats_s[0] == RAW[0]


def test_a_typed_bpm_grid_has_limits() -> None:
    with pytest.raises(GridError) as err:
        grid_from_bpm(100.0, 50.0, 10.0)
    assert err.value.reason == "not_enough_beats"
    with pytest.raises(GridError) as err2:
        grid_from_bpm(300.0, 0.0, 100000.0)
    assert err2.value.reason == "bpm_out_of_range"
    with pytest.raises(GridError) as err3:
        grid(GridChoice("bpm", 0, None))
    assert err3.value.reason == "bpm_missing"


def test_detected_versus_energy_grid() -> None:
    detected = grid(GridChoice("detected"), fallback=ENERGY)
    energy = grid(GridChoice("energy"), fallback=ENERGY)
    assert detected.fallback is None
    assert detected.beats_s == tuple(RAW)
    assert energy.fallback == "energy_grid"
    assert energy.source == "energy_grid"
    assert energy.beats_s[:2] == (0.1, 0.5)
    assert set(energy.downbeats_s) <= set(energy.beats_s)


def test_the_energy_grid_needs_a_stored_grid() -> None:
    with pytest.raises(GridError) as err:
        grid(GridChoice("energy"), fallback=None)
    assert err.value.reason == "no_fallback_grid"


def test_the_even_grid_marks_its_source() -> None:
    g = grid(GridChoice("even"))
    assert g.source == "even_grid"
    assert g.fallback == "even_grid"
    assert g.bpm == pytest.approx(120.0, abs=0.01)


def test_a_grid_with_one_beat_is_refused() -> None:
    with pytest.raises(GridError):
        effective_grid(
            [0.0, 0.5],
            [0.0],
            choice=GridChoice("detected", -1),
            fallback_grid=None,
            duration_s=1.0,
            model_name="m",
        )


def test_beats_per_bar_is_the_median_beats_between_downbeats() -> None:
    assert beats_per_bar(RAW_DOWN, RAW) == 4
    three = [0.0, 1.5, 3.0]
    assert beats_per_bar(three, [round(k * 0.5, 6) for k in range(7)]) == 3
    assert beats_per_bar([], RAW) == 4
    assert beats_per_bar([0.0, 100.0], [200.0]) == 4  # no beat falls in the bar


def test_the_choice_round_trips_through_the_plans_source() -> None:
    for choice in (
        GridChoice("detected", 1),
        GridChoice("detected", -1),
        GridChoice("energy", 0),
        GridChoice("even", 1),
        GridChoice("bpm", 0, 98.5),
    ):
        g = grid(choice, fallback=ENERGY)
        back = choice_from_plan(g.source, g.octave_total, 0, g.bpm)
        assert back.mode == choice.mode
        assert back.octave == choice.octave
        assert back.bpm == choice.bpm


def test_a_stored_plan_with_an_automatic_fold_keeps_only_the_owners_octave() -> None:
    assert choice_from_plan("beat_this:1", -1, -1, 120.0) == GridChoice("detected", 0)
    assert choice_from_plan("beat_this:1", 0, -1, 120.0) == GridChoice("detected", 1)
