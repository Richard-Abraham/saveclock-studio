"""Decisions over an ffprobe result of a silent 1080x1920 30 fps video (ported from the spike).

Pure over the probe dict, so the mezzanine check here and the master check of plan 007 share it.
"""

import itertools
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from saveclock.domain.framemath import FPS

TICKS = 30000 // FPS  # 1000 ticks per frame at timescale 30000
FRAME_S = 1.0 / FPS
WIDTH, HEIGHT = 1080, 1920
BOX_HEADER = 8
LARGE_SIZE_FLAG = 1


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


def moov_before_mdat(path: Path) -> bool:
    """+faststart: the top-level `moov` box precedes `mdat`."""
    seen: list[str] = []
    with path.open("rb") as fh:
        while True:
            hdr = fh.read(BOX_HEADER)
            if len(hdr) < BOX_HEADER:
                break
            size, kind = struct.unpack(">I4s", hdr)
            seen.append(kind.decode("latin1"))
            if size == LARGE_SIZE_FLAG:
                size = struct.unpack(">Q", fh.read(8))[0]
                fh.seek(size - 16, 1)
            elif size == 0:
                break
            else:
                fh.seek(size - BOX_HEADER, 1)
    return "moov" in seen and "mdat" in seen and seen.index("moov") < seen.index("mdat")


def pts_deltas(pts: Sequence[int]) -> list[int]:
    s = sorted(pts)
    return [b - a for a, b in itertools.pairwise(s)]


def video_checks(probe: dict[str, Any], total_frames: int, *, tolerance: int = 0) -> list[Check]:
    """QM-060..063 and 077. A mezzanine passes `tolerance=1`: the count may differ by one frame."""
    streams = probe["streams"]
    vids = [s for s in streams if s["codec_type"] == "video"]
    auds = [s for s in streams if s["codec_type"] == "audio"]
    checks = [
        Check(
            "QM-077 streams: 1 video, 0 audio, nothing else", len(vids) == 1 and len(streams) == 1
        )
    ]
    if len(vids) != 1:
        return checks
    v = vids[0]
    checks.append(Check("QM-077 no audio", not auds))
    checks.append(
        Check(
            "QM-060 H.264 High yuv420p 1080x1920 SAR 1:1",
            v["codec_name"] == "h264"
            and v.get("profile") == "High"
            and v["pix_fmt"] == "yuv420p"
            and (v["width"], v["height"]) == (WIDTH, HEIGHT)
            and v.get("sample_aspect_ratio", "1:1") in ("1:1", "N/A"),
            f"{v['codec_name']}/{v.get('profile')}/{v['pix_fmt']}/{v['width']}x{v['height']}"
            f"/sar={v.get('sample_aspect_ratio')}",
        )
    )
    checks.append(Check("QM-060 moov before mdat (+faststart)", bool(probe["moov_first"])))
    checks.append(
        Check(
            "QM-061 r_frame_rate = avg_frame_rate = 30/1",
            v["r_frame_rate"] == "30/1" and v["avg_frame_rate"] == "30/1",
            f"{v['r_frame_rate']} {v['avg_frame_rate']}",
        )
    )
    bad = [d for d in pts_deltas(probe["pts"]) if d != TICKS]
    checks.append(
        Check(
            f"QM-061 packet PTS deltas all {TICKS} ticks (tb {v.get('time_base')})",
            v.get("time_base") == "1/30000" and not bad,
            f"{len(bad)} off, first {bad[:3]}",
        )
    )
    nb = int(v["nb_read_frames"])
    checks.append(
        Check(
            "QM-062 nb_read_frames == plan",
            abs(nb - total_frames) <= tolerance,
            f"{nb} vs {total_frames}",
        )
    )
    dur = float(probe["format"]["duration"])
    checks.append(
        Check(
            "QM-063 duration within 1 frame",
            abs(dur - total_frames * FRAME_S) <= (1 + tolerance) * FRAME_S + 1e-9,
            f"{dur:.6f} vs {total_frames * FRAME_S:.6f}",
        )
    )
    return checks
