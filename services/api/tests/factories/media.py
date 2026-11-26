"""Real media files for FFmpeg tests, made with the pinned FFmpeg (never checked in)."""

from pathlib import Path

from saveclock.adapters.ffmpeg import Tools, ffmpeg_cmd, run
from tests.factories.audio import click_track


def make(
    tools: Tools, out: Path, *args: str, src: Path | None = None, pre: list[str] | None = None
) -> Path:
    """`ffmpeg [pre] [-i src] args out`; every call goes through the audited runner."""
    cmd = ffmpeg_cmd(tools, *(pre or []), *(["-i", str(src)] if src else []), *args, str(out))
    run(cmd, 120)
    return out


def wav_source(tmp: Path, duration: float = 20.0, bpm: float = 120.0) -> Path:
    path = tmp / "src.wav"
    click_track(path, bpm=bpm, duration=duration)
    return path


def encode(tools: Tools, tmp: Path, name: str, *codec_args: str, duration: float = 20.0) -> Path:
    return make(tools, tmp / name, *codec_args, src=wav_source(tmp, duration))


def mp3_with_cover(tools: Tools, tmp: Path) -> Path:
    cover = make(
        tools,
        tmp / "cover.jpg",
        "-frames:v",
        "1",
        pre=["-f", "lavfi", "-i", "color=c=red:s=64x64"],
    )
    return make(
        tools,
        tmp / "covered.mp3",
        *("-i", str(cover), "-map", "0:a", "-map", "1:v", "-c:a", "libmp3lame", "-c:v", "copy"),
        *("-id3v2_version", "3"),
        src=wav_source(tmp),
    )


def mp4_with_video(tools: Tools, tmp: Path) -> Path:
    return make(
        tools,
        tmp / "withvideo.mp4",
        *("-f", "lavfi", "-i", "testsrc=size=64x64:rate=10:duration=20"),
        *("-map", "1:v", "-map", "0:a", "-c:v", "libx264", "-c:a", "aac", "-shortest"),
        src=wav_source(tmp),
    )
