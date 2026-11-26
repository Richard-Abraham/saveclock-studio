"""The verification measurements on real media made with the pinned FFmpeg (no database)."""

from pathlib import Path

import pytest

from saveclock.adapters import dsp
from saveclock.adapters import verify_media as vm
from saveclock.adapters.ffmpeg import Tools, ffmpeg_cmd, probe_video, run
from saveclock.domain import verify as v
from tests.factories import media
from tests.factories.audio import click_track
from tests.factories.render import Rendered, render_plan, solid_stock

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]
MOVING = "overlay=x='mod(t*300,W-20)':y='mod(t*213,H-20)'"


@pytest.fixture(scope="module")
def rendered(ffmpeg_tools: Tools, tmp_path_factory: pytest.TempPathFactory) -> Rendered:
    tmp = tmp_path_factory.mktemp("verify-media")
    return render_plan(ffmpeg_tools, tmp, solid_stock(ffmpeg_tools, tmp / "clips"), seconds=15)


def synth(tools: Tools, out: Path, graph: str, *inputs: str) -> Path:
    """A small H.264 mp4 from lavfi sources (generated test media, never untrusted input)."""
    args = [a for src in inputs for a in ("-f", "lavfi", "-i", src)]
    run(
        ffmpeg_cmd(
            tools,
            *args,
            *("-filter_complex", graph, "-map", "[v]", "-an"),
            *("-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p"),
            *("-r", "30", "-movflags", "+faststart", str(out)),
        ),
        120,
    )
    return out


def test_the_master_probe_passes_every_block_check_and_carries_the_hashes(
    ffmpeg_tools: Tools, rendered: Rendered
) -> None:
    probe = vm.probe_master(ffmpeg_tools, rendered.master)
    results = v.master_checks(probe, rendered.plan.total_frames)
    assert not [r for r in results if not r.ok]
    assert len(probe["packet_hashes"]) == rendered.plan.total_frames
    assert len(probe["frame_pts_hash"]) == 64
    plain = probe_video(ffmpeg_tools, rendered.master)  # the mezzanine check does not pay for them
    assert set(plain) == {"streams", "format", "pts", "moov_first"}


def test_a_good_master_decodes_cleanly_and_a_damaged_one_does_not(
    ffmpeg_tools: Tools, rendered: Rendered, tmp_path: Path
) -> None:
    assert vm.decode_null(ffmpeg_tools, rendered.master) == ""
    damaged = tmp_path / "damaged.mp4"
    data = bytearray(rendered.master.read_bytes())
    for i in range(len(data) // 2, len(data) // 2 + 4000):
        data[i] = 0xFF
    damaged.write_bytes(bytes(data))
    assert v.playable_check(vm.decode_null(ffmpeg_tools, damaged)).ok is False


def test_gray_frames_show_a_peak_at_every_planned_cut(
    ffmpeg_tools: Tools, rendered: Rendered
) -> None:
    frames = vm.decode_gray(ffmpeg_tools, rendered.master)
    assert frames.shape == (rendered.plan.total_frames, vm.GRAY_H, vm.GRAY_W)
    diffs = dsp.frame_diffs(frames)
    planned = [c.out_start_frame for c in rendered.plan.cuts[1:]]
    report = v.detect_cuts(diffs, planned)
    assert [c.offset for c in report.cuts] == [0] * len(planned)
    assert v.unplanned_candidates(diffs, planned) == []


def test_black_frames_are_found_and_counted(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    clip = synth(
        ffmpeg_tools, tmp_path / "black.mp4",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "color=c=0x48c048:s=320x568:r=30:d=1", "color=c=black:s=320x568:r=30:d=0.4",
        "color=c=0x48c048:s=320x568:r=30:d=1",
    )  # fmt: skip
    assert vm.blackdetect(ffmpeg_tools, clip) == [12]
    assert v.black_report([12]).ok is False


def test_a_still_stretch_is_frozen_and_a_moving_clip_is_not(
    ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    still = synth(
        ffmpeg_tools, tmp_path / "still.mp4", "[0:v]null[v]", "color=c=0x4848d0:s=320x568:r=30:d=3"
    )
    frozen = vm.freezedetect(ffmpeg_tools, still, 3.0)
    assert frozen
    assert v.freeze_report(frozen).level is v.Level.BLOCK
    moving = synth(
        ffmpeg_tools, tmp_path / "moving.mp4", f"[0:v][1:v]{MOVING}[v]",
        "color=c=0x4848d0:s=320x568:r=30:d=3", "color=c=white:s=20x20:r=30:d=3",
    )  # fmt: skip
    assert vm.freezedetect(ffmpeg_tools, moving, 3.0) == []


def test_loudness_and_silence_are_measured(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    wav = tmp_path / "gap.wav"
    gap = r"aevalsrc=if(between(t\,2\,5)\,0\,0.5*sin(2*PI*440*t)):d=8:s=44100"  # 3 s of silence
    media.make(ffmpeg_tools, wav, "-ac", "1", "-ar", "44100", pre=["-f", "lavfi", "-i", gap])
    lufs, peak = vm.ebur128(ffmpeg_tools, wav, "wav")
    assert lufs is not None
    assert -30 < lufs < -5
    assert peak is not None
    assert peak <= 0.0
    silences = vm.silencedetect(ffmpeg_tools, wav, "wav", total_s=8.0)
    assert len(silences) == 1
    assert abs(silences[0] - 3.0) < 0.1
    assert vm.silencedetect(ffmpeg_tools, wav, "wav", start_s=0.0, dur_s=1.5, total_s=1.5) == []


def test_the_mono_decode_is_8_khz_and_the_click_offset_is_found(
    ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    wav = tmp_path / "clicks.wav"
    click_track(wav, bpm=120.0, duration=6.0)
    whole = vm.decode_mono8k(ffmpeg_tools, wav, "wav")
    assert len(whole) == 6 * dsp.XCORR_SR
    part = vm.decode_mono8k(ffmpeg_tools, wav, "wav", start_s=1.0, dur_s=3.0)
    assert len(part) == 3 * dsp.XCORR_SR
    assert abs(dsp.xcorr_offset(whole[8000:32000], part)) < 0.001
