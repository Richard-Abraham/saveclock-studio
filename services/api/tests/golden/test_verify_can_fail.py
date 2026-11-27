"""The verifier can fail, on real media: a master whose cuts are two frames off, a master with ten
black frames, and a master with a two-second freeze each trip the Block check that names them,
while the good master passes every Block."""

from pathlib import Path

import pytest

from saveclock.adapters.ffmpeg import MP4_FMT, Tools, ffmpeg_cmd, render_cmd, run
from saveclock.domain.edit_plan import EditPlan
from saveclock.services.render_job import verify_master
from tests.factories.render import SOLID, Rendered, render_plan, solid_stock

pytestmark = [pytest.mark.golden, pytest.mark.ffmpeg]


@pytest.fixture(scope="module")
def good(ffmpeg_tools: Tools, tmp_path_factory: pytest.TempPathFactory) -> Rendered:
    tmp = tmp_path_factory.mktemp("can-fail")
    return render_plan(ffmpeg_tools, tmp, solid_stock(ffmpeg_tools, tmp / "clips"), seconds=15)


def block_ids(tools: Tools, plan: EditPlan, master: Path) -> set[str]:
    doc = verify_master(tools, plan, master)
    return {c["id"] for c in doc["checks"] if not c["ok"] and c["level"] == "block"}


def reencode(tools: Tools, src: Path, out: Path, vf: str) -> Path:
    """The good master through a video filter, encoded again like the render (CFR 30, GOP 60)."""
    run(
        ffmpeg_cmd(
            tools,
            *("-f", MP4_FMT, "-i", str(src)),
            *("-vf", vf),
            *("-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high"),
            *("-pix_fmt", "yuv420p", "-r", "30", "-fps_mode", "cfr", "-g", "60"),
            *("-video_track_timescale", "30000", "-an", "-movflags", "+faststart", str(out)),
        ),
        300,
    )
    return out


def test_the_good_master_passes_every_block(ffmpeg_tools: Tools, good: Rendered) -> None:
    assert block_ids(ffmpeg_tools, good.plan, good.master) == set()


def test_cuts_two_frames_off_are_a_qm_064_block(
    ffmpeg_tools: Tools, good: Rendered, tmp_path: Path
) -> None:
    """Render the plan with one cut boundary two frames later (the shot before it two frames
    longer, the shot after it two shorter): the file is a valid video of the right length, so only
    the cut check can see it."""
    plan = good.plan
    k = 3
    cuts = list(plan.cuts)
    cuts[k - 1] = cuts[k - 1].model_copy(update={"out_end_frame": cuts[k - 1].out_end_frame + 2})
    cuts[k] = cuts[k].model_copy(update={"out_start_frame": cuts[k].out_start_frame + 2})
    shifted = plan.model_copy(update={"cuts": cuts})
    # the good render's mezzanines, one per colour (pool clip c00N is colour SOLID[N])
    paths = [
        good.master.parent / f"mezz_{SOLID[int(c.clip.provider_id[1:])]}.mp4" for c in shifted.cuts
    ]
    wrong = tmp_path / "shifted.mp4"
    run(
        render_cmd(ffmpeg_tools, shifted, paths, wrong, progress=tmp_path / "p.txt", threads=2), 300
    )
    assert "QM-064" in block_ids(ffmpeg_tools, plan, wrong)  # judged against the planned frames


def test_ten_black_frames_are_a_qm_070_block(
    ffmpeg_tools: Tools, good: Rendered, tmp_path: Path
) -> None:
    black = reencode(
        ffmpeg_tools, good.master, tmp_path / "black.mp4",
        "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(n,100,109)'",
    )  # fmt: skip
    assert "QM-070" in block_ids(ffmpeg_tools, good.plan, black)


def test_a_two_second_freeze_is_a_qm_071_block(
    ffmpeg_tools: Tools, good: Rendered, tmp_path: Path
) -> None:
    frozen = reencode(
        ffmpeg_tools, good.master, tmp_path / "frozen.mp4", "loop=loop=60:size=1:start=100"
    )
    assert "QM-071" in block_ids(ffmpeg_tools, good.plan, frozen)
