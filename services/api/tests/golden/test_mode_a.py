"""QM-067, QM-068, QM-087 on the real chain: the 128 BPM master with Mode A from three source types.

The measurements here are independent of the service's own numbers: the output and the song are
decoded again with the pinned FFmpeg and the offsets come from our own cross-correlation call; the
packet hashes come from ffprobe on the published files. An AAC-LC m4a is stream-copied (the output
audio packets are the source's), an mp3 and a wav are encoded once to AAC-LC 48 kHz.
"""

import json

import pytest

from saveclock.adapters import dsp
from saveclock.adapters import verify_media as vm
from saveclock.adapters.ffmpeg import MP4_FMT, Tools
from tests.integration.render_harness import Renders, SourceKind

pytestmark = [pytest.mark.golden, pytest.mark.ffmpeg]
FRAME_S = 1 / 30
AAC_FRAME_S = 1024 / 48000


@pytest.mark.parametrize("kind", ["m4a", "mp3", "wav"])
async def test_mode_a_keeps_the_sync_and_never_touches_the_video(
    golden: Renders, ffmpeg_tools: Tools, kind: SourceKind
) -> None:
    d = golden.draft
    pid = await d.drafted(
        pid=await golden.upload_source(kind, bpm=128.0, seconds=30.0), duration=30
    )
    plan = await d.plan(pid)
    rid = await golden.ready(pid)
    assert (await golden.mode_a(rid)).status_code == 202
    await golden.run_remux(await golden.job_of(rid, "remux"))
    out, master = golden.path(rid, "with_song.mp4"), golden.path(rid, "master.mp4")
    source = d.env.blob_root / "songs" / str(pid) / f"source.{kind}"
    dur = plan.total_frames / 30

    # exactly one video and one AAC-LC audio stream
    streams = vm.probe_remux(ffmpeg_tools, out)["streams"]
    assert sorted(s["codec_type"] for s in streams) == ["audio", "video"]
    audio = next(s for s in streams if s["codec_type"] == "audio")
    assert (audio["codec_name"], audio["profile"]) == ("aac", "LC")
    if kind != "m4a":
        assert audio["sample_rate"] == "48000"

    # the video is a bit-exact copy of the silent master (QM-087)
    assert vm.packet_hashes(ffmpeg_tools, out, MP4_FMT, "v:0") == vm.packet_hashes(
        ffmpeg_tools, master, MP4_FMT, "v:0"
    )
    if kind == "m4a":  # the audio is a stream copy: the output packets are a run of the source's
        heard = vm.packet_hashes(ffmpeg_tools, out, MP4_FMT, "a:0")
        assert (
            vm.find_run(vm.packet_hashes(ffmpeg_tools, source, MP4_FMT, "a:0"), heard) is not None
        )

    # offsets at t~1 s and t~dur-1 s, drift per 60 s, duration within one AAC frame
    got = vm.decode_mono8k(ffmpeg_tools, out, MP4_FMT)
    want = vm.decode_mono8k(
        ffmpeg_tools, source, kind if kind != "m4a" else MP4_FMT, plan.audio.trim.start_s, dur
    )
    start, end, drift = dsp.onset_offsets(want, got, dur)
    assert abs(start) <= FRAME_S
    assert abs(end) <= FRAME_S
    assert abs(drift) <= FRAME_S
    assert abs(len(got) / dsp.XCORR_SR - dur) <= AAC_FRAME_S + 1e-3
    checks = json.loads((await golden.render_row(rid))["v"])["mode_a"]["checks"]
    assert not [c for c in checks if not c["ok"] and c["level"] == "block"]
    print(  # shown with -s: the evidence line of this source type
        f"GOLDEN mode A {kind}: offset {start * 1e3:.2f} ms at 1 s, {end * 1e3:.2f} ms at end, "
        f"drift {drift * 1e3:.2f} ms/60 s (limit 33.3)"
    )
