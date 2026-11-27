"""Plan 011: a first downbeat near 0.0 starts the segment at 0.0 and keeps the full length."""

from dataclasses import replace
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from saveclock.cli.commands import _show_text
from saveclock.cli.schema import ShowOut, ShowPlan, ShowProject
from saveclock.domain.grid import GridChoice, GridView, effective_grid
from saveclock.domain.plan_validator import blocking, validate_plan
from saveclock.domain.planner import (
    PlanError,
    align_leading_beat,
    build_plan,
    room_s,
    snap_start,
)
from saveclock.services.plans import Basis, estimate_cuts, grid_for, initial_state, length_notice
from tests.unit.domain.plan_support import inputs, one_section, pool, uniform_grid

PERIOD = 0.46875  # 128 BPM


def shifted(first: float, bpm: float = 128.0, seconds: float = 190.0) -> GridView:
    g = uniform_grid(bpm, seconds)
    beats = tuple(round(b + first, 6) for b in g.beats_s)
    return replace(g, beats_s=beats, downbeats_s=beats[::4])


def basis(
    duration: float,
    first: float,
    requested: int,
    *,
    fallback: str | None = None,
) -> Basis:
    n = int((duration - first) / PERIOD)
    beats = [round(first + i * PERIOD, 6) for i in range(n)]
    beat_map: dict[str, Any] = {"raw": {"beats_s": beats, "downbeats_s": beats[::4]}}
    if fallback:
        beat_map["grid"] = {"beats_s": list(beats)}
    analysis: Any = SimpleNamespace(
        beat_map=beat_map,
        fallback=fallback,
        model="m",
        model_version="1",
        tempo_octave_adjust=0,
        sections=[{"id": "s1", "start_s": 0.0, "end_s": duration, "energy": "e2"}],
        energy_curve=[0.5] * int(duration * 2),
    )
    project: Any = SimpleNamespace(options={"duration": requested})
    song: Any = SimpleNamespace(duration_s=duration)
    return Basis(project, song, analysis, None, [])


@pytest.mark.unit
def test_the_exact_case_a_30_s_song_with_a_downbeat_at_0_02_drafts_30_s_from_0() -> None:
    b = basis(30.0, 0.02, 30)
    grid = grid_for(b, GridChoice("detected"))
    assert snap_start(grid, 0.0, 30, 30.0) == 0.0
    assert initial_state(b).length_s == 30
    assert estimate_cuts(b, initial_state(b)) > 0
    # the beats run past the end so the last cut has its end beat
    inp = replace(
        inputs(shifted(0.02), one_section("e3"), start_s=0.0, seconds=30, clips=pool(40)),
        song_duration_s=30.0,
    )
    built = build_plan(inp)
    plan = built.plan
    assert plan.total_frames == 900
    assert plan.cuts[0].out_start_frame == 0
    assert plan.cuts[0].beat_ref.t_s == 0.0
    assert 0.02 not in plan.beat_grid.beats_s
    assert plan.beat_grid.beats_s[0] == 0.0
    assert plan.beat_grid.downbeats_s[0] == 0.0
    found = validate_plan(plan, allow_repeats=built.pool_exhausted, beats_s=plan.beat_grid.beats_s)
    assert not blocking(found)
    frames = [c.out_start_frame for c in plan.cuts] + [900]
    assert all(b - a >= 15 for a, b in pairwise(frames))
    assert frames[-1] == 900


@pytest.mark.unit
def test_a_30_s_song_with_a_late_first_downbeat_drafts_15_s_and_says_so() -> None:
    b = basis(30.0, 0.8, 30)
    assert initial_state(b).length_s == 15
    with pytest.raises(PlanError, match="segment_out_of_range"):
        snap_start(grid_for(b, GridChoice("detected")), 0.0, 30, 30.0)
    assert length_notice(30, 15) == {"requested_s": 30, "drafted_s": 15}
    assert length_notice(30, 30) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("bpm", "d0", "near"),
    [
        (128.0, 0.46, True),
        (128.0, 0.46875, True),  # exactly one beat period: the limit itself is near
        (128.0, 0.48, False),
        (60.0, 0.5, True),  # the 0.5 s cap beats the 1 s period
        (60.0, 0.51, False),
        (0.0, 0.5, True),  # no tempo: only the cap applies
        (0.0, 0.51, False),
    ],
)
def test_the_near_zero_boundary(bpm: float, d0: float, near: bool) -> None:
    grid = GridView((d0, d0 + 1.0), (d0,), bpm, "t", None, 0)
    aligned = align_leading_beat(grid, 0.0)
    assert (aligned.downbeats_s[0] == 0.0) is near
    assert room_s(grid, 30.0) == (30.0 if near else 30.0 - d0)


@pytest.mark.unit
def test_a_downbeat_at_zero_is_left_alone() -> None:
    grid = shifted(0.0)
    assert align_leading_beat(grid, 0.0) == grid


@pytest.mark.unit
def test_a_segment_not_at_zero_keeps_its_grid() -> None:
    grid = shifted(0.02)
    assert align_leading_beat(grid, 0.02) == grid


@pytest.mark.unit
def test_an_energy_grid_follows_the_same_rule() -> None:
    near = basis(30.0, 0.02, 30, fallback="energy_grid")
    assert initial_state(near).length_s == 30
    grid = grid_for(near, GridChoice("energy"))
    assert grid.source == "energy_grid"
    assert align_leading_beat(grid, 0.0).downbeats_s[0] == 0.0
    late = basis(30.0, 0.6, 30, fallback="energy_grid")
    assert initial_state(late).length_s == 15


@pytest.mark.unit
def test_a_double_time_octave_step_tightens_the_limit() -> None:
    beats = [round(0.3 + i * PERIOD, 6) for i in range(64)]
    downs = beats[::4]

    def grid(octave: int) -> GridView:
        return effective_grid(
            beats, downs, choice=GridChoice("detected", octave), fallback_grid=None,
            duration_s=30.0, model_name="m",
        )  # fmt: skip

    assert align_leading_beat(grid(0), 0.0).downbeats_s[0] == 0.0  # limit 0.469
    assert align_leading_beat(grid(1), 0.0).downbeats_s[0] == 0.3  # limit 0.234


@pytest.mark.unit
def test_explicit_duration_replans() -> None:
    grid = shifted(0.02)
    assert snap_start(grid, 5.0, 30, 30.0) == 0.0
    for length, song in ((30, 29.99), (31, 30.0)):
        with pytest.raises(PlanError, match="segment_out_of_range"):
            snap_start(grid, 0.0, length, song)


@pytest.mark.unit
def test_the_show_text_prints_the_notice_only_while_it_is_true() -> None:
    def show(frames: int, flags: dict[str, Any]) -> str:
        project = ShowProject(
            id="p", title=None, ui_status="draft", status_reason=None, flags=flags, options={}
        )
        out = ShowOut(
            project=project, song=None, analysis=None, keywords=None, render=None,
            plan=ShowPlan(version=1, frozen=False, total_frames=frames, n_cuts=2),
        )  # fmt: skip
        return _show_text(out)

    flag = {"length_reduced": {"requested_s": 30, "drafted_s": 15}}
    assert (
        "  notice: drafted 15 s, not the 30 s requested: "
        "the song is too short for 30 s from its first downbeat"
    ) in show(450, flag)
    assert "notice" not in show(450, {})
    assert "notice" not in show(900, flag)  # a later edit of the length silences it


# fmt: off
# Captured from the unmodified planner (plan 011 step 0): d0 -> (start, cuts, content hash)
BASELINE: dict[float, tuple[float, list[tuple[float, int]], str]] = {
    0.02: (
        0.02,
        [
            (0.02, 0), (0.9575, 28), (1.895, 56), (2.8325, 84),
            (3.77, 113), (4.7075, 141), (5.645, 169), (6.5825, 197),
            (7.52, 225), (8.4575, 253), (9.395, 281), (10.3325, 309),
            (11.27, 338), (12.2075, 366), (13.145, 394), (14.0825, 422),
            (15.02, 450), (15.9575, 478), (16.895, 506), (17.8325, 534),
            (18.77, 563), (19.7075, 591), (20.645, 619), (21.5825, 647),
            (22.52, 675), (23.4575, 703), (24.395, 731), (25.3325, 759),
            (26.27, 788), (27.2075, 816), (28.145, 844), (29.0825, 872),
        ],
        "156ec3039ab38a43fd930921346d7f852b4e83bb9382c54e48c976e79e676481",
    ),
    0.0: (
        0.0,
        [
            (0.0, 0), (0.9375, 28), (1.875, 56), (2.8125, 84),
            (3.75, 113), (4.6875, 141), (5.625, 169), (6.5625, 197),
            (7.5, 225), (8.4375, 253), (9.375, 281), (10.3125, 309),
            (11.25, 338), (12.1875, 366), (13.125, 394), (14.0625, 422),
            (15.0, 450), (15.9375, 478), (16.875, 506), (17.8125, 534),
            (18.75, 563), (19.6875, 591), (20.625, 619), (21.5625, 647),
            (22.5, 675), (23.4375, 703), (24.375, 731), (25.3125, 759),
            (26.25, 788), (27.1875, 816), (28.125, 844), (29.0625, 872),
        ],
        "4a3732b5da708dc58a7175c7bc50a7458bf045d9489359de60aa355cc22e1fa8",
    ),
}
# fmt: on


@pytest.mark.unit
@pytest.mark.parametrize("d0", [0.02, 0.0])
def test_a_long_song_plans_byte_identically_to_before(d0: float) -> None:
    grid = shifted(d0, 128.0, 180.0)
    start, cuts, digest = BASELINE[d0]
    assert snap_start(grid, 0.0, 30, 180.0) == start
    built = build_plan(inputs(grid, one_section("e3"), start_s=start, seconds=30, clips=pool(40)))
    assert [(c.beat_ref.t_s, c.out_start_frame) for c in built.plan.cuts] == cuts
    assert built.plan.content_hash == digest
