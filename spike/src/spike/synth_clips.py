"""12 solid-colour synthetic source clips + 2 testsrc2 clips (T-0.3) and audio sources.

``lavfi`` is used here and ONLY here, on our own generated sources (SEC-011); it is never
applied to untrusted input.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from spike.ffwrap import Tools, ffmpeg_cmd, run
from spike.vcodec import source_encode

# 12 colours chosen by farthest-point sampling in BT.709 YUV over a 4^3 RGB grid
# (min pairwise YUV distance 94.4 on a 0-255 scale).
PALETTE: list[tuple[int, int, int]] = [
    (0, 0, 255),
    (255, 255, 0),
    (0, 255, 255),
    (255, 0, 0),
    (0, 85, 0),
    (255, 170, 255),
    (0, 255, 0),
    (255, 0, 255),
    (85, 0, 85),
    (170, 255, 170),
    (85, 170, 255),
    (170, 85, 0),
]
NTSC = "30000/1001"


@dataclass(frozen=True)
class ClipSpec:
    name: str
    fps: str
    size: str
    sar: str
    gop: int
    source: str  # "color" or "testsrc2"
    colour_idx: int | None = None
    seconds: int = 16


# fps 24, 25, 30000/1001, 50, 60 (+30); sizes 720p, 360p, 1080x1920, 1080p; SAR 1 and 4:3; GOP 12/250
_PROPS: list[tuple[str, str, str, int]] = [
    ("24", "1280x720", "1", 12),
    ("25", "640x360", "1", 250),
    (NTSC, "1920x1080", "4/3", 12),
    ("50", "1080x1920", "1", 12),
    ("60", "1920x1080", "1", 250),
    ("30", "1280x720", "4/3", 12),
    ("24", "1080x1920", "1", 250),
    ("25", "1920x1080", "4/3", 12),
    (NTSC, "640x360", "1", 12),
    ("50", "1280x720", "4/3", 250),
    ("60", "1080x1920", "1", 12),
    ("30", "640x360", "1", 250),
]


def clip_specs() -> list[ClipSpec]:
    specs = [
        ClipSpec(f"solid_{i:02d}", fps, size, sar, gop, "color", i)
        for i, (fps, size, sar, gop) in enumerate(_PROPS)
    ]
    specs.append(ClipSpec("testsrc2_2398", "24000/1001", "1280x720", "4/3", 12, "testsrc2"))
    specs.append(ClipSpec("testsrc2_2997", NTSC, "1920x1080", "3/2", 250, "testsrc2"))
    return specs


def lavfi_source(spec: ClipSpec) -> str:
    if spec.source == "color":
        assert spec.colour_idx is not None
        r, g, b = PALETTE[spec.colour_idx]
        return f"color=c=0x{r:02x}{g:02x}{b:02x}:s={spec.size}:r={spec.fps}:d={spec.seconds}"
    return f"testsrc2=s={spec.size}:r={spec.fps}:d={spec.seconds}"


def make_clip(tools: Tools, codec: str, spec: ClipSpec, out: Path) -> None:
    cmd = ffmpeg_cmd(
        tools,
        *("-f", "lavfi", "-i", lavfi_source(spec)),  # our own generated source only
        *("-vf", f"setsar={spec.sar},format=yuv420p"),
        *source_encode(codec, spec.gop),
        *("-an", "-movflags", "+faststart", str(out)),
    )
    run(cmd, 300)


def make_clips(tools: Tools, codec: str, out_dir: Path) -> dict[str, Path]:
    """Generate (idempotently) the clip set; existing files are reused so every build sees the
    same input bytes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for spec in clip_specs():
        p = out_dir / f"{spec.name}.mp4"
        if not p.exists():
            make_clip(tools, codec, spec, p)
        paths[spec.name] = p
    return paths


AUDIO_FORMATS: dict[str, list[str]] = {
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "mp3": ["-c:a", "libmp3lame", "-b:a", "192k"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "flac": ["-c:a", "flac"],
}


def make_audio_sources(tools: Tools, wav: Path, out_dir: Path) -> dict[str, Path]:
    """From a synthetic WAV: m4a (AAC-LC), mp3, ogg, flac, plus the WAV itself."""
    from spike.ffwrap import input_args

    out_dir.mkdir(parents=True, exist_ok=True)
    res: dict[str, Path] = {"wav": wav}
    for ext, enc in AUDIO_FORMATS.items():
        p = out_dir / f"{wav.stem}.{ext}"
        if not p.exists():
            run(ffmpeg_cmd(tools, *input_args(wav), "-map", "0:a:0", "-vn", *enc, str(p)), 120)
        res[ext] = p
    return res
