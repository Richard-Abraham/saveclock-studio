from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from saveclock.domain.grid import GridChoice
from saveclock.domain.plan_ops import (
    OPS,
    AnyOp,
    OpContext,
    PlanOpError,
    ReplanState,
    SetKeywords,
    apply_ops,
    refuse_keyword_extras,
)

CTX = OpContext(song_duration_s=100.0, has_energy_grid=True, cut_count=10)
START = ReplanState(GridChoice(), start_s=4.0, length_s=30, density=0)
ADAPTER: TypeAdapter[Any] = TypeAdapter(AnyOp)


def op(**body: Any) -> Any:
    return ADAPTER.validate_python(body)


def run(state: ReplanState, *ops: dict[str, Any]) -> ReplanState:
    return apply_ops(state, [op(**o) for o in ops], CTX)


def test_set_tempo_octave() -> None:
    assert run(START, {"op": "set_tempo_octave", "octave": -1}).grid.octave == -1
    with pytest.raises(ValidationError):
        op(op="set_tempo_octave", octave=2)


def test_an_octave_on_a_typed_tempo_is_refused() -> None:
    typed = run(START, {"op": "set_bpm", "bpm": 100})
    with pytest.raises(PlanOpError) as err:
        run(typed, {"op": "set_tempo_octave", "octave": 1})
    assert err.value.reason == "octave_with_typed_bpm"


def test_set_bpm_takes_exactly_one_of_two_arguments() -> None:
    assert run(START, {"op": "set_bpm", "bpm": 98.5}).grid == GridChoice("bpm", 0, 98.5)
    assert run(START, {"op": "set_bpm", "use_even_grid": True}).grid.mode == "even"
    for body in ({}, {"bpm": 90, "use_even_grid": True}):
        with pytest.raises(ValidationError):
            op(op="set_bpm", **body)
    for bad in (39, 301):
        with pytest.raises(ValidationError):
            op(op="set_bpm", bpm=bad)


def test_the_even_grid_keeps_the_owners_octave_unless_a_typed_tempo_was_set() -> None:
    halved = run(START, {"op": "set_tempo_octave", "octave": -1})
    assert run(halved, {"op": "set_bpm", "use_even_grid": True}).grid.octave == -1
    typed = run(START, {"op": "set_bpm", "bpm": 90})
    assert run(typed, {"op": "set_bpm", "use_even_grid": True}).grid.octave == 0


def test_use_detected_beats_toggles_the_fallback_grid() -> None:
    assert run(START, {"op": "use_detected_beats", "on": False}).grid.mode == "energy"
    energy = run(START, {"op": "use_detected_beats", "on": False})
    assert run(energy, {"op": "use_detected_beats", "on": True}).grid.mode == "detected"
    none = OpContext(100.0, False, 10)
    with pytest.raises(PlanOpError) as err:
        apply_ops(START, [op(op="use_detected_beats", on=False)], none)
    assert err.value.reason == "no_fallback_grid"


def test_set_density_is_bounded() -> None:
    assert run(START, {"op": "set_density", "level": 1}).density == 1
    for bad in (-3, 2):
        with pytest.raises(ValidationError):
            op(op="set_density", level=bad)


def test_set_segment_with_a_start_and_a_duration() -> None:
    got = run(START, {"op": "set_segment", "start_s": 20.5, "duration_s": 60})
    assert (got.start_s, got.length_s, got.auto_start) == (20.5, 60, False)
    keep = run(START, {"op": "set_segment", "start_s": 9.0})
    assert keep.length_s == 30


def test_set_segment_auto_picks_the_start_later() -> None:
    got = run(START, {"op": "set_segment", "auto": True, "duration_s": 15})
    assert (got.auto_start, got.length_s) == (True, 15)
    with pytest.raises(ValidationError):
        op(op="set_segment", auto=True, start_s=3.0)
    with pytest.raises(ValidationError):
        op(op="set_segment")


@pytest.mark.parametrize(
    "body",
    [
        {"op": "set_segment", "start_s": 90.0, "duration_s": 30},  # runs past the song
        {"op": "set_segment", "start_s": 1.0, "duration_s": 45},  # not 15, 30 or 60
        {"op": "set_segment", "auto": True, "duration_s": 120},  # longer than the song
    ],
)
def test_set_segment_out_of_range(body: dict[str, Any]) -> None:
    with pytest.raises(PlanOpError) as err:
        run(START, body)
    assert err.value.reason == "segment_out_of_range"


def test_lock_clip_records_the_flag_and_checks_the_cut() -> None:
    got = run(START, {"op": "lock_clip", "cut_index": 3, "locked": True})
    assert got.locks == ((3, True),)
    with pytest.raises(PlanOpError) as err:
        run(START, {"op": "lock_clip", "cut_index": 10, "locked": True})
    assert err.value.reason == "no_such_cut"


def test_a_batch_is_all_or_nothing() -> None:
    with pytest.raises(PlanOpError):
        run(
            START,
            {"op": "set_density", "level": 1},
            {"op": "set_segment", "start_s": 99.0, "duration_s": 30},
        )
    assert START.density == 0  # the caller's state was never touched


def test_an_unknown_op_and_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        op(op="swap_clip", cut_index=1)
    with pytest.raises(ValidationError):
        op(op="set_density", level=0, surprise=1)


def test_the_registry_holds_exactly_the_phase_two_local_ops() -> None:
    assert set(OPS) == {
        "set_tempo_octave",
        "set_bpm",
        "use_detected_beats",
        "set_density",
        "set_segment",
        "lock_clip",
    }


def test_section_keywords_and_vibe_chips_are_refused_with_a_reason() -> None:
    plain = SetKeywords(op="set_keywords", keywords=["sea"])
    refuse_keyword_extras(plain)
    with pytest.raises(PlanOpError) as err:
        refuse_keyword_extras(SetKeywords(op="set_keywords", keywords=["sea"], section_id="s1"))
    assert err.value.reason == "section_keywords_not_supported"
    with pytest.raises(PlanOpError) as err2:
        refuse_keyword_extras(SetKeywords(op="set_keywords", keywords=["sea"], vibe_chips=["calm"]))
    assert err2.value.reason == "vibe_chips_not_supported"
    for bad in ([], ["Sea!"], ["a b"] * 9):
        with pytest.raises(ValidationError):
            SetKeywords(op="set_keywords", keywords=bad)
