"""probe_stock, sample_frames and the mezzanine command, with the pinned FFmpeg."""

from pathlib import Path
from typing import Any

import pytest

from saveclock.adapters import ffmpeg
from saveclock.adapters.ffmpeg import (
    MEZZ_VF,
    FfCanceled,
    FfError,
    FfTimeout,
    ProbeFailed,
    Tools,
    build_mezz,
    mezz_cmd,
    probe_stock,
    probe_video,
    sample_frames,
)
from saveclock.domain.windows import Window
from tests.factories.media import make

pytestmark = pytest.mark.ffmpeg
H264 = ("-c:v", "libx264", "-preset", "ultrafast", "-crf", "35", "-an")


def clip(
    tools: Tools, tmp: Path, name: str = "c.mp4", size: str = "720x1280", seconds: float = 4.0
) -> Path:
    return make(
        tools,
        tmp / name,
        *H264,
        pre=["-f", "lavfi", "-i", f"testsrc2=s={size}:r=30:d={seconds}"],
    )


def test_probe_stock_reads_size_duration_fps_and_bytes(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    path = clip(ffmpeg_tools, tmp_path)
    probe = probe_stock(ffmpeg_tools, path)
    assert (probe.width, probe.height) == (720, 1280)
    assert probe.duration_s == pytest.approx(4.0, abs=0.1)
    assert probe.fps == pytest.approx(30.0)
    assert probe.size_bytes == path.stat().st_size


def test_a_rotation_flag_swaps_the_displayed_size(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    landscape = clip(ffmpeg_tools, tmp_path, "land.mp4", "1280x720")
    rotated = make(
        ffmpeg_tools,
        tmp_path / "rot.mp4",
        "-c",
        "copy",
        pre=["-display_rotation", "90"],
        src=landscape,
    )
    assert (
        probe_stock(ffmpeg_tools, landscape).width,
        probe_stock(ffmpeg_tools, landscape).height,
    ) == (1280, 720)
    probe = probe_stock(ffmpeg_tools, rotated)
    assert (probe.width, probe.height) == (720, 1280)


def test_audio_next_to_the_video_is_fine_two_video_streams_are_not(
    ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    with_audio = make(
        ffmpeg_tools,
        tmp_path / "av.mp4",
        *("-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest"),
        pre=["-f", "lavfi", "-i", "testsrc2=s=720x1280:r=30:d=3", "-f", "lavfi", "-i", "sine=d=3"],
    )
    assert probe_stock(ffmpeg_tools, with_audio).width == 720
    two = make(
        ffmpeg_tools,
        tmp_path / "two.mp4",
        *("-map", "0:v", "-map", "1:v", "-c:v", "libx264", "-preset", "ultrafast"),
        pre=[
            *("-f", "lavfi", "-i", "testsrc2=s=720x1280:r=30:d=3"),
            *("-f", "lavfi", "-i", "testsrc2=s=720x1280:r=30:d=3"),
        ],
    )
    with pytest.raises(ProbeFailed, match="one video stream"):
        probe_stock(ffmpeg_tools, two)
    audio_only = make(
        ffmpeg_tools, tmp_path / "a.mp4", "-c:a", "aac", pre=["-f", "lavfi", "-i", "sine=d=2"]
    )
    with pytest.raises(ProbeFailed):
        probe_stock(ffmpeg_tools, audio_only)


def test_garbage_is_not_a_stock_clip(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00" * 200)
    with pytest.raises(ProbeFailed):
        probe_stock(ffmpeg_tools, bad)


def test_a_stream_without_size_or_duration_is_refused(
    monkeypatch: pytest.MonkeyPatch, ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    data: dict[str, Any] = {
        "streams": [{"codec_type": "video", "width": 0, "height": 0}],
        "format": {},
    }
    monkeypatch.setattr(ffmpeg, "_probe_json", lambda *a, **k: data)
    with pytest.raises(ProbeFailed, match="no size or duration"):
        probe_stock(ffmpeg_tools, tmp_path / "x.mp4")


def test_fraction_handles_bad_values() -> None:
    assert ffmpeg._fraction("30/1") == 30.0
    assert ffmpeg._fraction("0/0") is None
    assert ffmpeg._fraction("junk") is None
    assert ffmpeg._fraction(None) is None


def test_sample_frames_writes_one_224_wide_frame_per_second(
    ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    path = clip(ffmpeg_tools, tmp_path, seconds=5.0)
    frames = sample_frames(ffmpeg_tools, path, tmp_path / "frames", 1.0, 3)
    assert [f.name for f in frames] == ["frame_01.jpg", "frame_02.jpg", "frame_03.jpg"]
    from PIL import Image

    with Image.open(frames[0]) as img:
        assert img.size[0] == 224


def test_the_mezzanine_command_is_the_architecture_template(
    ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    cmd = mezz_cmd(ffmpeg_tools, tmp_path / "in.mp4", Window(0.2, 3.6), tmp_path / "out.mp4")
    text = " ".join(cmd)
    assert "-f mov,mp4,m4a,3gp,3g2,mj2 -i" in text
    assert "-ss 0.2 -t 3.6" in text
    assert MEZZ_VF in cmd
    assert "-r 30 -fps_mode cfr" in text
    assert "-c:v libx264 -preset veryfast -crf 14 -profile:v high" in text
    assert "-g 15 -keyint_min 15 -sc_threshold 0 -bf 2" in text
    assert "-video_track_timescale 30000 -movflags +faststart" in text
    assert cmd.count("-protocol_whitelist") == 1


def test_a_failed_encode_leaves_no_output_and_the_probe_reads_a_good_one(
    ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"\x00" * 100)
    out = tmp_path / "m.mp4"
    out.write_bytes(b"stale")
    with pytest.raises(FfError):
        build_mezz(ffmpeg_tools, broken, Window(0, 1), out)
    assert not out.exists()
    src = clip(ffmpeg_tools, tmp_path, seconds=3.0)
    build_mezz(ffmpeg_tools, src, Window(0.0, 2.0), out)
    probe = probe_video(ffmpeg_tools, out)
    assert probe["moov_first"] is True
    assert int(probe["streams"][0]["nb_read_frames"]) in {59, 60, 61}


def test_timeouts_and_cancels_pass_through_probes_and_clean_up_a_decode(
    monkeypatch: pytest.MonkeyPatch, ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    def timeout(*a: Any, **k: Any) -> None:
        raise FfTimeout("slow")

    def canceled(*a: Any, **k: Any) -> None:
        raise FfCanceled("stop")

    monkeypatch.setattr(ffmpeg, "run", timeout)
    with pytest.raises(FfTimeout):
        probe_stock(ffmpeg_tools, tmp_path / "x.mp4")
    out = tmp_path / "o.flac"
    out.write_bytes(b"partial")
    with pytest.raises(FfTimeout):
        ffmpeg.canonicalize(ffmpeg_tools, tmp_path / "x.wav", "wav", out)
    assert not out.exists()
    monkeypatch.setattr(ffmpeg, "run", canceled)
    with pytest.raises(FfCanceled):
        probe_stock(ffmpeg_tools, tmp_path / "x.mp4")
