"""Golden boundary frames of the planner for click tracks (the render itself is plan 007).

Derivation of `plan_frames.json` (ARCHITECTURE 11.1, done with exact arithmetic, not with
`framemath`): an e3 section cuts every 2 beats; the beat grid of a click track at B BPM is
`t_k = round(k * 60 / B, 6)`; the boundary of the cut on beat `k` is `floor(30 * t_k + 1/2)`.
At 128 BPM a beat is 0.46875 s = 14.0625 frames, so every 2 beats the boundaries are
28, 56, 84, 113 (112.5 rounds up), 141, 169, ... and 900 is the end. At 133.3 BPM the beat is
0.450113 s: 27, 54, 81, 108, ... A 60 s plan at 133.3 BPM with density +1 would need 67 cuts every
2 beats, so the step widens to 3 beats (the spike's 60-input rule). Each frame in the fixture was
checked against `Fraction` arithmetic when it was written; this test fails on any drift.
"""

import json
from decimal import Decimal
from fractions import Fraction
from math import floor
from pathlib import Path

import pytest

from tests.unit.domain.plan_support import inputs, one_section, uniform_grid

pytestmark = pytest.mark.golden
CASES = json.loads((Path(__file__).with_name("plan_frames.json")).read_text())


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_planner_output_equals_the_committed_boundaries(name: str) -> None:
    from saveclock.domain.planner import build_plan

    case = CASES[name]
    built = build_plan(
        inputs(
            uniform_grid(case["bpm"]),
            one_section("e3"),
            seconds=case["seconds"],
            density=case["density"],
        )
    )
    cuts = built.plan.cuts
    got = [
        {"beat_index": c.beat_ref.beat_index, "t_s": c.beat_ref.t_s, "frame": c.out_start_frame}
        for c in cuts
    ]
    assert got == case["cuts"]
    assert built.plan.total_frames == case["total_frames"]
    assert cuts[-1].out_end_frame == case["total_frames"]


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_committed_frames_follow_the_rule_in_exact_arithmetic(name: str) -> None:
    for cut in CASES[name]["cuts"][1:]:
        exact = floor(Fraction(Decimal(repr(cut["t_s"]))) * 30 + Fraction(1, 2))
        assert cut["frame"] == exact


def test_the_128_bpm_golden_starts_with_the_literal_of_the_derivation() -> None:
    frames = [c["frame"] for c in CASES["128bpm_30s_e3"]["cuts"]]
    assert frames[:5] == [0, 28, 56, 84, 113]
