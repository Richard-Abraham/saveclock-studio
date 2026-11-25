"""Normalise a source clip to the mezzanine (ARCHITECTURE 11 "Normalize" template)."""

from __future__ import annotations

from pathlib import Path

from spike.ffwrap import MP4_FMT, RunResult, Tools, ffmpeg_cmd, run
from spike.vcodec import mezz_encode

WINDOW_START_S = 1.0
WINDOW_LEN_S = 4.0
MEZZ_VF = (
    "fps=30,scale=1080:1920:force_original_aspect_ratio=increase:flags=bicubic,"
    "crop=1080:1920,setsar=1,format=yuv420p"
)


def mezz_cmd(tools: Tools, codec: str, src: Path, out: Path) -> list[str]:
    return ffmpeg_cmd(
        tools,
        *("-f", MP4_FMT, "-i", str(src)),
        *("-map", "0:v:0", "-an", "-sn", "-dn"),
        *("-ss", f"{WINDOW_START_S}", "-t", f"{WINDOW_LEN_S}"),
        *("-vf", MEZZ_VF),
        *("-r", "30", "-fps_mode", "cfr"),
        *mezz_encode(codec),
        *("-video_track_timescale", "30000", "-movflags", "+faststart", str(out)),
    )


def build_mezz(tools: Tools, codec: str, src: Path, out: Path) -> RunResult:
    return run(mezz_cmd(tools, codec, src, out), 300, rss=True)
