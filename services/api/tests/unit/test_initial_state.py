"""The draft's default length leaves room for the first downbeat (found by the plan 009 dry run)."""

from types import SimpleNamespace
from typing import Any

import pytest

from saveclock.domain.grid import GridChoice
from saveclock.domain.planner import PlanError, snap_start
from saveclock.services.plans import Basis, estimate_cuts, grid_for, initial_state


def basis(duration: float, first: float, requested: int) -> Basis:
    beats = [round(first + i * 0.46875, 6) for i in range(int((duration - first) / 0.46875))]
    analysis: Any = SimpleNamespace(
        beat_map={"raw": {"beats_s": beats, "downbeats_s": beats[::4]}},
        fallback=None,
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
def test_a_30_s_song_with_a_downbeat_at_0_02_drafts_15_s_not_a_failure() -> None:
    b = basis(30.0, 0.02, 30)
    state = initial_state(b)
    assert state.length_s == 15
    assert estimate_cuts(b, state) > 0


@pytest.mark.unit
def test_a_song_with_room_keeps_the_requested_length() -> None:
    assert initial_state(basis(45.0, 0.02, 30)).length_s == 30
    assert initial_state(basis(30.0, 0.0, 30)).length_s == 30  # a downbeat at 0 leaves all of it


@pytest.mark.unit
def test_an_explicit_length_that_cannot_fit_is_still_refused() -> None:
    grid = grid_for(basis(30.0, 0.02, 30), GridChoice("detected"))
    with pytest.raises(PlanError, match="segment_out_of_range"):
        snap_start(grid, 0.0, 30, 30.0)  # snap_start is unchanged
