"""QM-064: every planned cut shows its colour change on exactly its planned frame (0-frame error).

The chain is the real one: a click track -> upload -> validate -> analysis grid (the click picker
stands in for Beat This) -> the draft over four solid-colour clips -> `POST /renders` ->
`render_master` -> the master decoded one pixel per frame. The expected cut frames come from an
independent `Fraction` oracle over the plan's own beat times, not from the planner or the renderer;
the colours come from the mezzanines themselves, measured. The cases are those of
`spike/results/render-9.0.x.json` (tempo x length; `lead_frames` stays 0).
"""

import json
from decimal import Decimal
from fractions import Fraction
from math import floor

import numpy as np
import pytest

from saveclock.adapters.ffmpeg import Tools
from saveclock.domain.edit_plan import EditPlan
from tests.factories.render import changes, decode_colours, measured_colour, nearest
from tests.integration.render_harness import Renders

pytestmark = [pytest.mark.golden, pytest.mark.ffmpeg]
CASES = [(bpm, seconds) for bpm in (120.0, 128.0, 133.3) for seconds in (30, 60)]


def oracle_cut_frames(plan: EditPlan) -> list[int]:
    """`floor((t_i - t_0) * 30 + 1/2) - lead` in exact arithmetic from the beat times."""
    t0 = Fraction(Decimal(repr(plan.audio.trim.start_s)))
    return [
        floor((Fraction(Decimal(repr(c.beat_ref.t_s))) - t0) * 30 + Fraction(1, 2))
        - plan.lead_frames
        for c in plan.cuts[1:]
    ]


@pytest.mark.parametrize(("bpm", "seconds"), CASES, ids=[f"{b}bpm-{s}s" for b, s in CASES])
async def test_every_cut_lands_on_its_exact_frame(
    golden: Renders, ffmpeg_tools: Tools, bpm: float, seconds: int
) -> None:
    d = golden.draft
    pid = await d.drafted(bpm=bpm, seconds=float(seconds), duration=seconds)
    plan = await d.plan(pid)
    rid = await golden.ready(pid)
    master = golden.path(rid, "master.mp4")
    row = await golden.render_row(rid)

    expected = oracle_cut_frames(plan)
    assert [c.out_start_frame for c in plan.cuts[1:]] == expected  # the plan is the oracle's
    assert plan.total_frames == seconds * 30
    assert len({c.clip.provider_id for c in plan.cuts}) >= 3  # a real mix of colours

    keys = sorted({c.clip.mezzanine_key for c in plan.cuts})
    palette = np.asarray([measured_colour(ffmpeg_tools, d.env.blob_root / k) for k in keys])
    colours = decode_colours(ffmpeg_tools, master)
    assert len(colours) == plan.total_frames  # nb_read_frames == total_frames
    labels = nearest(colours, palette)
    detected = changes(labels)
    assert detected == expected  # 0-frame error on every cut, and no other change

    shots = [labels[c.out_start_frame] for c in plan.cuts]
    assert shots == [keys.index(c.clip.mezzanine_key) for c in plan.cuts]  # right clip in each shot
    verify = json.loads(row["v"])
    assert verify["max_cut_error_frames"] == 0
    assert verify["duration_delta_frames"] == 0
    assert verify["timing"]["render_ms"] > 0
    print(  # shown with -s: the evidence line of this case
        f"GOLDEN {bpm} bpm {seconds} s: {len(expected)} cuts, worst cut error 0 frames, "
        f"render {verify['timing']['render_ms']} ms, verify {verify['timing']['verify_ms']} ms"
    )
