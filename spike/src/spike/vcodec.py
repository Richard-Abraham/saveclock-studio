"""H.264 encoder choice and per-role argument sets.

ARCHITECTURE 11 templates use ``libx264``. The Fedora ``/usr/bin/ffmpeg`` 8.1.3 has no libx264
(only ``libopenh264``, no ``-crf``/``-preset``/``-bf``/``-sc_threshold``), so the harness takes
the template args verbatim for libx264 and an explicit, labelled fallback for libopenh264.
"""

from __future__ import annotations

import re

from spike.ffwrap import Tools, ffmpeg_cmd, run

X264 = "libx264"
OPENH264 = "libopenh264"


def pick_vcodec(tools: Tools, forced: str = "auto") -> str:
    if forced != "auto":
        return forced
    out = run(ffmpeg_cmd(tools, "-encoders"), 30).stdout.decode()
    return X264 if re.search(r"\blibx264\b", out) else OPENH264


def mezz_encode(codec: str) -> list[str]:
    """Mezzanine encode args (template: crf 14, GOP 15, no scene-cut keyframes, 2 B-frames)."""
    if codec == X264:
        return [
            *("-c:v", X264, "-preset", "veryfast", "-crf", "14", "-profile:v", "high"),
            *("-g", "15", "-keyint_min", "15", "-sc_threshold", "0", "-bf", "2"),
        ]
    return [
        *("-c:v", OPENH264, "-profile:v", "high", "-b:v", "20M", "-g", "15"),
        *("-allow_skip_frames", "0"),
    ]


def render_encode(codec: str) -> list[str]:
    """Final-render encode args (template: crf 20, High, yuv420p, GOP 60)."""
    if codec == X264:
        return [
            *("-c:v", X264, "-preset", "veryfast", "-crf", "20", "-profile:v", "high"),
            *("-pix_fmt", "yuv420p"),
        ]
    return [
        *("-c:v", OPENH264, "-profile:v", "high", "-pix_fmt", "yuv420p", "-b:v", "8M"),
        *("-allow_skip_frames", "0"),
    ]


def source_encode(codec: str, gop: int) -> list[str]:
    """Encode args for our own synthetic source clips."""
    if codec == X264:
        return [*("-c:v", X264, "-preset", "ultrafast", "-crf", "18", "-g", str(gop))]
    return [*("-c:v", OPENH264, "-b:v", "4M", "-g", str(gop), "-allow_skip_frames", "0")]
