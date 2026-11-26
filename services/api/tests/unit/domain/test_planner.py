import itertools
import math
import random
from decimal import Decimal
from fractions import Fraction

import pytest

from saveclock.domain.grid import GridView
from saveclock.domain.plan_hash import canonical_json
from saveclock.domain.plan_validator import Level, Violation, blocking, validate_plan
from saveclock.domain.planner import (
    PlanError,
    SectionIn,
    build_plan,
    fit_length,
    plan_beats,
    plan_cuts,
    snap_start,
)
from saveclock.domain.rules import cut_rules_v1 as rules
from tests.unit.domain.plan_support import (
    inputs,
    one_section,
    plan,
    sections,
    uniform_grid,
)

FPS = 30


def oracle_frame(t_s: float, t0_s: float) -> int:
    """floor((t - t0) * 30 + 1/2) in exact arithmetic from the decimal text of the times."""
    delta = (Fraction(Decimal(repr(t_s))) - Fraction(Decimal(repr(t0_s)))) * FPS + Fraction(1, 2)
    return math.floor(delta)


def test_the_128_bpm_worked_example_is_a_literal() -> None:
    # ARCHITECTURE 11.1: 0.46875 s beats; every beat gives 14, 28, 42, 56, 70, 84, 98, 113 ...
    # (summing rounded durations would give 896 at the end)
    beat = 60.0 / 128.0
    exact = [oracle_frame(i * beat, 0.0) for i in range(9)]
    assert exact == [0, 14, 28, 42, 56, 70, 84, 98, 113]
    assert oracle_frame(64 * beat, 0.0) == 900


def test_every_boundary_matches_the_exact_arithmetic_oracle() -> None:
    for bpm in (100.0, 128.0, 133.3, 150.0):
        grid = uniform_grid(bpm)
        for slot in plan_cuts(grid, one_section("e3"), 0.0, 900, density=0)[1:]:
            assert slot.start_frame == oracle_frame(slot.t_s, 0.0), (bpm, slot)


def test_128_bpm_30_s_hits_900_and_the_lengths_sum_to_it() -> None:
    slots = plan_cuts(uniform_grid(128.0), one_section("e3"), 0.0, 900, density=0)
    assert slots[0].start_frame == 0
    assert slots[-1].end_frame == 900
    lengths = [s.end_frame - s.start_frame for s in slots]
    assert sum(lengths) == 900
    assert {s.start_frame for s in slots} >= {28, 56, 84, 113}  # every 2 beats: 112.5 -> 113


@pytest.mark.parametrize(("bpm", "beats_per_cut"), [(120.0, 1), (128.0, 2), (133.3, 2)])
def test_the_stride_rule_of_the_spike(bpm: float, beats_per_cut: int) -> None:
    """Every beat up to 120 BPM (beat >= 15 frames), every 2 beats above (e3, density +1)."""
    grid = uniform_grid(bpm)
    slots = plan_cuts(grid, one_section("e3"), 0.0, 900, density=1)
    beat_index = {t: i for i, t in enumerate(grid.beats_s)}
    steps = {beat_index[b.t_s] - beat_index[a.t_s] for a, b in itertools.pairwise(slots)}
    assert min(steps) == beats_per_cut


def test_133_bpm_60_s_needs_the_widened_step_and_stays_in_the_cap() -> None:
    grid = uniform_grid(133.3)
    slots = plan_cuts(grid, one_section("e3"), 0.0, 1800, density=1)
    assert len(slots) <= rules.MAX_SHOTS
    beat_index = {t: i for i, t in enumerate(grid.beats_s)}
    steps = {beat_index[b.t_s] - beat_index[a.t_s] for a, b in itertools.pairwise(slots)}
    assert steps == {3}  # stride 2 would need 67 cuts


def test_the_widening_always_ends() -> None:
    # a 180 BPM e4 song at density +1 wants more than 60 cuts in 60 s
    slots = plan_cuts(uniform_grid(180.0), one_section("e4"), 0.0, 1800, density=1)
    assert len(slots) <= rules.MAX_SHOTS


def test_the_widening_gives_up_when_it_cannot_reach_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("saveclock.domain.planner.MAX_WIDEN", 2)
    monkeypatch.setattr(rules, "MAX_SHOTS", 1)
    with pytest.raises(PlanError) as err:
        plan_cuts(uniform_grid(120.0), one_section("e3"), 0.0, 900, density=0)
    assert err.value.reason == "cut_cap_unreachable"


@pytest.mark.parametrize("bpm", [70.0, 100.0, 128.0, 150.0, 180.0])
def test_property_every_cut_is_on_a_beat_and_valid(bpm: float) -> None:
    """Over densities, labels, lengths and section layouts: no BLOCK, no WARN, cuts on beats."""
    rng = random.Random(int(bpm * 10))  # noqa: S311 - a seeded test fixture
    for density, label, seconds in itertools.product(
        (-2, -1, 0, 1), ("e1", "e2", "e3", "e4"), (15, 30, 60)
    ):
        for layout in range(3):
            cut_at = sorted(rng.uniform(2.0, seconds) for _ in range(layout))
            edges = [0.0, *cut_at, 400.0]
            labels = [label, *rng.sample(("e1", "e2", "e3", "e4"), layout)]
            secs = [
                SectionIn(f"s{i}", a, b, lab)
                for i, (a, b, lab) in enumerate(zip(edges, edges[1:], labels, strict=False), 1)
            ]
            built = build_plan(
                inputs(uniform_grid(bpm), secs, density=density, seconds=seconds, seed=layout)
            )
            plan_ = built.plan
            assert (
                blocking(
                    validate_plan(
                        plan_, allow_repeats=built.pool_exhausted, beats_s=plan_.beat_grid.beats_s
                    )
                )
                == []
            )
            beats = set(plan_.beat_grid.beats_s)
            assert all(c.beat_ref.t_s in beats for c in plan_.cuts)
            lengths = [c.out_end_frame - c.out_start_frame for c in plan_.cuts]
            assert min(lengths) >= rules.MIN_SHOT_FRAMES
            assert sum(lengths) == plan_.total_frames == seconds * FPS
            assert len(plan_.cuts) <= rules.MAX_SHOTS
            if bpm > rules.EVERY_BEAT_MAX_BPM:  # no every-beat cutting over 120 BPM
                beat_index = {t: i for i, t in enumerate(plan_.beat_grid.beats_s)}
                gaps = [
                    beat_index[b.beat_ref.t_s] - beat_index[a.beat_ref.t_s]
                    for a, b in itertools.pairwise(plan_.cuts)
                ]
                assert min(gaps, default=2) >= 2


@pytest.mark.parametrize("bpm", [70.0, 90.0, 100.0, 120.0, 128.0, 140.0])
@pytest.mark.parametrize("label", ["e1", "e2", "e3", "e4"])
def test_property_density_is_monotonic_below_the_cap(bpm: float, label: str) -> None:
    grid = uniform_grid(bpm)
    counts = [len(plan_cuts(grid, one_section(label), 0.0, 900, density=d)) for d in (-2, -1, 0, 1)]
    assert counts == sorted(counts), (bpm, label, counts)


def test_the_cap_can_make_density_non_monotonic_a_known_limit() -> None:
    """Finding (plan 006 P6-13): when the 60-cut cap widens a busy level, that level can end up
    with fewer cuts than the level below it. 180 BPM e4, 60 s: 47 cuts at -1, 46 at 0."""
    grid = uniform_grid(180.0)
    counts = [len(plan_cuts(grid, one_section("e4"), 0.0, 1800, density=d)) for d in (-1, 0)]
    assert counts[1] < counts[0] <= rules.MAX_SHOTS


@pytest.mark.parametrize("label", ["e1", "e2", "e3", "e4"])
def test_no_shot_exceeds_its_maximum_when_the_cap_does_not_bite(label: str) -> None:
    built = plan(128.0, label, density=-2)
    assert [v for v in built.warnings if v.rule == "max_shot"] == []


def test_the_first_shot_is_at_least_a_bar_in_a_quiet_opening() -> None:
    for label in ("e1", "e2"):
        slots = plan_cuts(uniform_grid(128.0), one_section(label), 0.0, 900, density=1)
        bar = round(4 * 1800 / 128.0)
        assert slots[0].end_frame >= bar - 1


def test_a_loud_opening_may_cut_before_a_bar() -> None:
    slots = plan_cuts(uniform_grid(128.0), one_section("e3"), 0.0, 900, density=1)
    assert slots[0].end_frame < round(4 * 1800 / 128.0)


def test_each_section_opens_on_a_downbeat() -> None:
    secs = sections(("e2", 0.0, 7.5), ("e4", 7.5, 15.0), ("e3", 15.0, 60.0))
    grid = uniform_grid(128.0)
    built = build_plan(inputs(grid, secs))
    firsts: dict[str, int] = {}
    for c in built.plan.cuts:
        firsts.setdefault(c.section.id, c.index)
    assert all(built.plan.cuts[i].beat_ref.kind == "downbeat" for i in firsts.values())
    assert set(firsts) == {"s1", "s2", "s3"}
    assert built.warnings == []


def test_the_last_cut_moves_to_the_last_downbeat() -> None:
    # e2, density +1 at 128 BPM steps every 2 beats; the grid ends mid bar so the last
    # boundary is moved to a downbeat that leaves at least a beat
    slots = plan_cuts(uniform_grid(128.0), one_section("e2"), 0.0, 900, density=1)
    last = slots[-1]
    assert last.kind == "downbeat" or last.end_frame - last.start_frame >= 14


def test_the_planner_is_deterministic() -> None:
    a = build_plan(inputs(uniform_grid(133.3), one_section("e3"), seconds=60, density=1))
    b = build_plan(inputs(uniform_grid(133.3), one_section("e3"), seconds=60, density=1))
    assert canonical_json(a.plan) == canonical_json(b.plan)


def test_every_density_factor_and_label_has_a_rule() -> None:
    assert set(rules.DENSITY_FACTOR) == {-2, -1, 0, 1}
    assert set(rules.INTERVALS) == set(rules.LABELS) == set(rules.MAX_SHOT_FRAMES)


def test_a_segment_must_start_on_a_grid_beat() -> None:
    with pytest.raises(PlanError) as err:
        plan_cuts(uniform_grid(128.0), one_section(), 0.1, 900, density=0)
    assert err.value.reason == "segment_start_not_on_grid"


def test_snap_start_chooses_the_nearest_downbeat_that_fits() -> None:
    grid = uniform_grid(120.0)  # downbeats every 2 s
    assert snap_start(grid, 5.1, 30, 180.0) == 6.0
    assert snap_start(grid, 179.0, 30, 180.0) == max(d for d in grid.downbeats_s if d + 30 <= 180.0)
    with pytest.raises(PlanError):
        snap_start(grid, 0.0, 30, 10.0)


def test_fit_length_picks_the_largest_that_fits() -> None:
    assert fit_length(60, 600.0) == 60
    assert fit_length(60, 45.0) == 30
    assert fit_length(30, 20.0) == 15
    with pytest.raises(PlanError):
        fit_length(30, 10.0)


def test_plan_beats_includes_the_end_beat() -> None:
    grid = uniform_grid(120.0)
    beats = plan_beats(grid, 0.0, 450)
    assert beats[0] == 0.0
    assert beats[-1] == 15.0


def test_sections_missing_fall_back_to_one_mid_section() -> None:
    slots = plan_cuts(uniform_grid(128.0), [], 0.0, 900, density=0)
    assert slots[0].label == "e2"


def test_beats_before_the_first_or_after_the_last_section_take_their_label() -> None:
    secs = [SectionIn("a", 4.0, 8.0, "e1"), SectionIn("b", 8.0, 12.0, "e4")]
    slots = plan_cuts(uniform_grid(128.0), secs, 0.0, 900, density=0)
    assert slots[0].label == "e1"
    assert slots[-1].label == "e4"


def test_a_grid_that_is_too_short_is_refused() -> None:
    grid = GridView((0.0,), (0.0,), 120.0, "x", None, 0)
    with pytest.raises(PlanError):
        plan_cuts(grid, one_section(), 0.5, 450, density=0)


def test_a_plan_with_a_block_is_a_planner_bug(monkeypatch: pytest.MonkeyPatch) -> None:
    block = Violation(Level.BLOCK, "frame_rule", "forced", 1)
    monkeypatch.setattr("saveclock.domain.planner.validate_plan", lambda *_a, **_k: [block])
    with pytest.raises(PlanError) as err:
        build_plan(inputs(uniform_grid(128.0), one_section(), seconds=30))
    assert err.value.reason == "plan_invalid"
    assert err.value.violations == [block]


def test_a_lead_shifts_every_boundary_and_the_plan_stays_valid() -> None:
    built = build_plan(inputs(uniform_grid(128.0), one_section(), seconds=30, lead=1))
    plain = build_plan(inputs(uniform_grid(128.0), one_section(), seconds=30))
    assert built.plan.lead_frames == 1
    assert built.plan.cuts[1].out_start_frame == plain.plan.cuts[1].out_start_frame - 1
