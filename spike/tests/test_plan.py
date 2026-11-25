from pathlib import Path

import numpy as np
import pytest

from spike.annot import write_beats
from spike.framemath import cut_frames
from spike.plan import MAX_SHOTS, MIN_SHOT_FRAMES, build_plan

MEZZ = [120] * 12


def make_beats(tmp: Path, bpm: float, seconds: float) -> Path:
    n = int(seconds * bpm / 60.0)
    t = np.arange(n, dtype=np.float64) * 60.0 / bpm
    p = tmp / "x.beats"
    write_beats(p, t, np.arange(n) % 4 == 0)
    return p


@pytest.mark.parametrize(("bpm", "stride"), [(120.0, 1), (128.0, 2), (133.3, 2)])
def test_stride_rule(tmp_path: Path, bpm: float, stride: int) -> None:
    plan = build_plan("t", make_beats(tmp_path, bpm, 70), 30, 0, 0, 1, MEZZ)
    assert plan.stride == stride


def test_128_bpm_30s_hits_900_exactly(tmp_path: Path) -> None:
    plan = build_plan("t", make_beats(tmp_path, 128.0, 70), 30, 0, 0, 1, MEZZ)
    assert plan.total_frames == 900
    assert plan.frames == cut_frames(plan.beat_times, plan.t0, 30, 0)
    assert sum(s.length for s in plan.shots) == 900


@pytest.mark.parametrize("lead", [0, 1])
@pytest.mark.parametrize("bpm", [120.0, 128.0, 133.3])
def test_min_shot_cap_and_adjacent_clips(tmp_path: Path, bpm: float, lead: int) -> None:
    for seconds in (30, 60):
        plan = build_plan("t", make_beats(tmp_path, bpm, 130), seconds, 1, lead, 3, MEZZ)
        assert all(s.length >= MIN_SHOT_FRAMES for s in plan.shots)
        assert len(plan.shots) <= MAX_SHOTS
        assert all(a.clip != b.clip for a, b in zip(plan.shots, plan.shots[1:], strict=False))
        assert all(s.in_frame + s.length <= 120 for s in plan.shots)
        assert sum(s.length for s in plan.shots) == seconds * 30
        assert plan.frames[0] == 0


def test_cap_forces_longer_stride_at_133_bpm_60s(tmp_path: Path) -> None:
    plan = build_plan("t", make_beats(tmp_path, 133.3, 130), 60, 0, 0, 3, MEZZ)
    assert plan.stride == 3  # stride 2 would need 67 cuts > 60
