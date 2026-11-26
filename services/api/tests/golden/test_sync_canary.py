"""QM-069, the sync canary: a synthetic project whose every shot starts with a white flash frame
and whose audio carries a 1 kHz click at that cut's exact sample.

The project is rendered with the production command, the song is remuxed on with the production
command (a wav, so the one AAC-LC transcode path), and both are decoded again through the pinned
FFmpeg: the time of every flash frame and the time of its click must differ by at most one frame
(33.3 ms). QUALITY QM-069 also asks for a mobile-like player path; DECISIONS §8g dropped the phone
check, so the phone path is *not measured* (P7-11) and G2 evidence must say so.
"""

import wave
from pathlib import Path

import numpy as np
import pytest

from saveclock.adapters.ffmpeg import (
    MP4_FMT,
    Tools,
    build_mezz,
    ffmpeg_cmd,
    remux_cmd,
    render_cmd,
    run,
)
from saveclock.adapters.verify_media import decode_mono8k
from saveclock.domain.planner import build_plan
from saveclock.domain.windows import Window
from tests.factories.render import COLOURS, SOLID, decode_colours
from tests.unit.domain.plan_support import inputs, one_section, pool, uniform_grid

pytestmark = [pytest.mark.golden, pytest.mark.ffmpeg]
SR = 48000
CLICK_S = 0.003
FRAME_S = 1 / 30
LIMIT_S = FRAME_S  # QM-069: at most one frame


def flash_mezzanine(tools: Tools, tmp: Path, name: str) -> Path:
    """A solid mezzanine whose frame 0 is white."""
    src = tmp / f"flash_{name}_src.mp4"
    run(
        ffmpeg_cmd(
            tools,
            *("-f", "lavfi", "-i", f"color=c={COLOURS[name]}:s=720x1280:r=30:d=6"),
            *("-vf", "drawbox=x=0:y=0:w=iw:h=ih:c=white:t=fill:enable='eq(n,0)',format=yuv420p"),
            *("-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", str(src)),
        ),
        120,
    )
    out = tmp / f"flash_{name}.mp4"
    build_mezz(tools, src, Window(0.0, 5.4), out)
    return out


def click_wav(path: Path, frames: list[int], total_frames: int) -> None:
    """A mono 48 kHz wav with a 1 kHz burst starting at the exact sample of each cut frame
    (`frame / 30 * 48000 = frame * 1600`, an integer)."""
    x = np.zeros(total_frames * SR // 30)
    burst = 0.8 * np.sin(2 * np.pi * 1000 * np.arange(int(CLICK_S * SR)) / SR)
    for f in frames:
        x[f * 1600 : f * 1600 + len(burst)] = burst
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


@pytest.mark.parametrize("bpm", [120.0, 133.3])
def test_flash_frame_and_click_agree_within_one_frame_for_every_cut(
    ffmpeg_tools: Tools, tmp_path: Path, bpm: float
) -> None:
    clips = pool(len(SOLID), frames=162)
    built = build_plan(inputs(uniform_grid(bpm), one_section("e3"), seconds=15, clips=clips)).plan
    cuts = [
        c.model_copy(update={"clip": c.clip.model_copy(update={"in_frame": 0})}) for c in built.cuts
    ]
    plan = built.model_copy(update={"cuts": cuts})  # every shot starts at the clip's white frame
    mezz = {
        clips[i].provider_id: flash_mezzanine(ffmpeg_tools, tmp_path, n)
        for i, n in enumerate(SOLID)
    }
    master = tmp_path / "master.mp4"
    run(
        render_cmd(
            ffmpeg_tools, plan, [mezz[c.clip.provider_id] for c in cuts], master,
            progress=tmp_path / "p.txt", threads=2,
        ),
        300,
    )  # fmt: skip
    starts = [c.out_start_frame for c in cuts]
    song = tmp_path / "song.wav"
    click_wav(song, starts, plan.total_frames)
    out = tmp_path / "with_song.mp4"
    run(
        remux_cmd(
            ffmpeg_tools, master, song, "wav", audio_start_s=0.0, total_frames=plan.total_frames,
            out=out, aac_copy=False,
        ),
        60,
    )  # fmt: skip

    colours = decode_colours(ffmpeg_tools, out)
    flashes = [int(i) for i in np.flatnonzero((colours > 235).all(axis=1))]
    assert flashes == starts  # one white frame at the start of every shot, and nowhere else
    heard = decode_mono8k(ffmpeg_tools, out, MP4_FMT)
    worst = 0.0
    for f in starts:
        t = f / 30
        lo, hi = max(0, int((t - 0.1) * 8000)), int((t + 0.1) * 8000)
        window = np.abs(heard[lo:hi])
        onset = lo + int(np.argmax(window > 0.3))
        assert window.max() > 0.3, f"no click near {t:.3f} s"
        worst = max(worst, abs(onset / 8000 - t))
    assert worst <= LIMIT_S
    print(
        f"GOLDEN canary {bpm} bpm: {len(starts)} cuts, "
        f"worst flash-to-click {worst * 1e3:.2f} ms (limit 33.3)"
    )
