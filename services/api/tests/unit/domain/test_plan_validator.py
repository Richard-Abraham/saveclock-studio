from typing import Any

import pytest

from saveclock.domain import edit_plan as ep
from saveclock.domain.plan_validator import Level, Violation, blocking, validate_plan
from tests.unit.domain.plan_support import plan


def good() -> ep.EditPlan:
    return plan(128.0, seconds=30).plan


def check(p: ep.EditPlan, *, allow_repeats: bool = False) -> list[Violation]:
    return validate_plan(p, allow_repeats=allow_repeats, beats_s=p.beat_grid.beats_s)


def rules(violations: list[Violation], level: Level = Level.BLOCK) -> set[str]:
    return {v.rule for v in violations if v.level is level}


def with_cut(p: ep.EditPlan, i: int, **update: Any) -> ep.EditPlan:
    cuts = list(p.cuts)
    cuts[i] = cuts[i].model_copy(update=update)
    return p.model_copy(update={"cuts": cuts})


def test_the_planners_plan_has_no_violation_at_all() -> None:
    assert check(good()) == []


def test_invariant_1_first_cut_starts_at_zero() -> None:
    p = with_cut(good(), 0, out_start_frame=1)
    assert "starts_at_zero" in rules(check(p))


def test_invariant_1_cuts_are_contiguous() -> None:
    p = with_cut(good(), 0, out_end_frame=good().cuts[0].out_end_frame + 1)
    assert "contiguous" in rules(check(p))


def test_invariant_1_the_last_cut_ends_at_total() -> None:
    p = good()
    p = with_cut(p, len(p.cuts) - 1, out_end_frame=p.total_frames + 1)
    assert "ends_at_total" in rules(check(p))


def test_invariant_1_a_cut_has_at_least_one_frame() -> None:
    p = good()
    p = with_cut(p, 0, out_end_frame=0)
    assert "length" in rules(check(p))


def test_invariant_2_the_frame_rule_is_exact() -> None:
    p = good()
    p = with_cut(p, 1, out_start_frame=p.cuts[1].out_start_frame + 1)
    assert "frame_rule" in rules(check(p))


def test_invariant_2_a_float_boundary_is_blocked() -> None:
    p = good()
    cut = ep.Cut.model_construct(**{**dict(p.cuts[1]), "out_start_frame": 28.0})
    cuts = [p.cuts[0], cut, *p.cuts[2:]]
    assert "frame_int" in rules(check(p.model_copy(update={"cuts": cuts})))


def test_a_cut_must_sit_on_a_grid_beat() -> None:
    p = good()
    off = p.cuts[1].beat_ref.model_copy(update={"t_s": p.cuts[1].beat_ref.t_s + 0.001})
    assert "beat_on_grid" in rules(check(with_cut(p, 1, beat_ref=off)))


def test_the_kind_must_match_the_downbeats() -> None:
    p = good()
    wrong = p.cuts[1].beat_ref.model_copy(update={"kind": "downbeat"})
    assert "kind" in rules(check(with_cut(p, 1, beat_ref=wrong)))


def test_rounding_error_is_bounded_to_16_7_ms() -> None:
    p = good().model_copy(update={"lead_frames": 1})  # every boundary now one frame (33 ms) off
    assert "rounding_error" in rules(check(p))


def test_invariant_3_a_clip_must_cover_its_cut() -> None:
    p = good()
    clip = p.cuts[0].clip.model_copy(update={"mezzanine_frames": 10})
    assert "clip_fit" in rules(check(with_cut(p, 0, clip=clip)))


def test_invariant_4_repeats_only_when_allowed() -> None:
    p = good()
    again = with_cut(p, 1, clip=p.cuts[0].clip)
    assert "repeat" in rules(check(again))
    assert "repeat" not in rules(check(again, allow_repeats=True))


def test_invariant_5_audio_trim_matches_the_total() -> None:
    p = good()
    trim = p.audio.trim.model_copy(update={"duration_frames": p.total_frames - 1})
    assert "audio_trim" in rules(check(p.model_copy(update={"audio": ep.Audio(trim=trim)})))


def test_invariant_6_fps_and_resolution() -> None:
    p = good()
    assert "fps" in rules(check(p.model_copy(update={"fps": 25})))
    small = ep.Resolution(width=720, height=1280)
    assert "resolution" in rules(check(p.model_copy(update={"resolution": small})))


def test_sixty_one_cuts_are_refused() -> None:
    p = good()
    base = p.cuts[0]
    cuts = [
        base.model_copy(
            update={"index": i, "out_start_frame": i * 15, "out_end_frame": (i + 1) * 15}
        )
        for i in range(61)
    ]
    found = rules(check(p.model_copy(update={"cuts": cuts, "total_frames": 61 * 15})))
    assert "cut_count" in found


def test_a_fourteen_frame_shot_is_refused() -> None:
    p = good()
    p = with_cut(p, 0, out_end_frame=14)
    assert "min_shot" in rules(check(p))


def test_max_shot_and_short_shots_are_warnings_not_blocks() -> None:
    p = plan(128.0, "e1", density=-2).plan  # a calm opening: fine
    assert blocking(check(p)) == []
    long = with_cut(good(), 0, out_end_frame=good().cuts[0].out_end_frame)
    # a 100-frame shot in an e3 section is over its 90-frame maximum
    stretched = long.model_copy(
        update={
            "cuts": [
                long.cuts[0].model_copy(update={"out_end_frame": 100}),
                long.cuts[1].model_copy(update={"out_start_frame": 100}),
                *long.cuts[2:],
            ]
        }
    )
    found = check(stretched)
    assert "max_shot" in rules(found, Level.WARN)
    assert "max_shot" not in rules(found, Level.BLOCK)


def test_a_section_opened_off_a_downbeat_is_a_warning() -> None:
    p = good()
    sec = p.cuts[1].section.model_copy(update={"id": "s9"})
    beat = p.cuts[1].beat_ref.model_copy(update={"kind": "beat"})
    found = check(with_cut(p, 1, section=sec, beat_ref=beat))
    assert "section_start" in rules(found, Level.WARN)


def test_a_short_opening_in_a_quiet_section_is_a_warning() -> None:
    p = good()
    sec = p.cuts[0].section.model_copy(update={"label": "e1"})
    found = check(with_cut(p, 0, section=sec))
    assert "first_shot" in rules(found, Level.WARN)


def test_a_last_shot_under_a_beat_is_a_warning() -> None:
    p = good()
    n = len(p.cuts)
    cuts = list(p.cuts)
    cuts[n - 2] = cuts[n - 2].model_copy(update={"out_end_frame": p.total_frames - 5})
    cuts[n - 1] = cuts[n - 1].model_copy(update={"out_start_frame": p.total_frames - 5})
    assert "last_shot" in rules(check(p.model_copy(update={"cuts": cuts})), Level.WARN)


def test_a_grid_with_one_downbeat_has_no_bar_to_compare() -> None:
    p = good()
    grid = p.beat_grid.model_copy(update={"downbeats_s": p.beat_grid.downbeats_s[:1]})
    found = validate_plan(
        p.model_copy(update={"beat_grid": grid}), allow_repeats=False, beats_s=grid.beats_s
    )
    assert "first_shot" not in rules(found, Level.WARN)


@pytest.mark.parametrize("bpm", [70, 90, 100, 120, 128, 133.3, 150, 180])
def test_the_planner_output_is_valid_at_any_tempo(bpm: float) -> None:
    assert blocking(check(plan(bpm).plan)) == []
