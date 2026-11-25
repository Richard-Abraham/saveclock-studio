"""Post-render verification (QUALITY 3.3 QM-060..064, 077; ARCHITECTURE 11.2).

Pure decision logic is in small functions so it is unit-testable without ffmpeg.
"""

from __future__ import annotations

import hashlib
import itertools
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from spike.ffwrap import MP4_FMT, Tools, ffmpeg_cmd, probe_json, run
from spike.framemath import FPS, cut_frames, shot_lengths
from spike.plan import Plan

TICKS = 30000 // FPS  # 1000 ticks per frame at timescale 30000
FRAME_S = 1.0 / FPS
Rgb = npt.NDArray[np.float64]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def moov_before_mdat(path: Path) -> bool:
    """+faststart: the top-level ``moov`` box precedes ``mdat``."""
    seen: list[str] = []
    with path.open("rb") as fh:
        while True:
            hdr = fh.read(8)
            if len(hdr) < 8:
                break
            size, kind = struct.unpack(">I4s", hdr)
            seen.append(kind.decode("latin1"))
            if size == 1:
                size = struct.unpack(">Q", fh.read(8))[0]
                fh.seek(size - 16, 1)
            elif size == 0:
                break
            else:
                fh.seek(size - 8, 1)
    return "moov" in seen and "mdat" in seen and seen.index("moov") < seen.index("mdat")


def pts_deltas(pts: Sequence[int]) -> list[int]:
    s = sorted(pts)
    return [b - a for a, b in itertools.pairwise(s)]


def nearest_labels(colours: Rgb, palette: Rgb) -> npt.NDArray[np.int64]:
    d = np.linalg.norm(colours[:, None, :] - palette[None, :, :], axis=2)
    return np.argmin(d, axis=1).astype(np.int64)


def detected_changes(labels: Sequence[int]) -> list[int]:
    """Frame indices where the label differs from the previous frame."""
    return [i for i in range(1, len(labels)) if labels[i] != labels[i - 1]]


def compare_cuts(expected: Sequence[int], detected: Sequence[int]) -> dict[str, Any]:
    """Expected cut frames (f_1..) vs detected changes. 0-frame error required for PASS;
    1-frame deviations are reported separately."""
    exact = sorted(set(expected) & set(detected))
    missing = sorted(set(expected) - set(detected))
    extra = sorted(set(detected) - set(expected))
    dev1: list[dict[str, int]] = []
    other_missing: list[int] = []
    for f in missing:
        near = [d for d in extra if abs(d - f) == 1]
        if near:
            dev1.append({"planned": f, "found": near[0], "delta": near[0] - f})
        else:
            other_missing.append(f)
    return {
        "exact": len(exact),
        "expected": len(expected),
        "missing": missing,
        "extra": extra,
        "deviations_1f": dev1,
        "unmatched": other_missing,
        "pass": not missing and not extra,
    }


def decode_colours(tools: Tools, path: Path) -> Rgb:
    """One area-averaged pixel per frame; ffmpeg's stdout is read (output pipe is not an input
    protocol, so ``-protocol_whitelist file`` does not need ``pipe``)."""
    cmd = ffmpeg_cmd(
        tools,
        *("-f", MP4_FMT, "-i", str(path), "-map", "0:v:0"),
        *("-vf", "scale=1:1:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"),
    )
    raw = run(cmd, 300).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.float64)


def measure_palette(tools: Tools, mezz_paths: Sequence[Path]) -> Rgb:
    """Measured mean colour of each solid mezzanine (robust to the YUV/RGB conversion)."""
    rows = [np.median(decode_colours(tools, p), axis=0) for p in mezz_paths]
    return np.asarray(rows, dtype=np.float64)


def min_pair_distance(palette: Rgb) -> float:
    n = len(palette)
    return float(
        min(np.linalg.norm(palette[i] - palette[j]) for i in range(n) for j in range(i + 1, n))
    )


def probe_video(tools: Tools, path: Path) -> dict[str, Any]:
    """Everything the video checks need from ffprobe (one call each for stream, packets, frames)."""
    info = probe_json(
        tools,
        path,
        "-count_frames",
        "-show_format",
        "-show_streams",
        "-show_entries",
        "stream=codec_type,codec_name,profile,pix_fmt,width,height,sample_aspect_ratio,"
        "r_frame_rate,avg_frame_rate,time_base,nb_read_frames,start_time:"
        "format=duration,format_name,nb_streams",
    )
    pk = probe_json(
        tools,
        path,
        "-select_streams",
        "v:0",
        "-show_packets",
        "-show_data_hash",
        "sha256",
        "-show_entries",
        "packet=pts,dts,duration,flags,data_hash",
    )
    fr = probe_json(
        tools,
        path,
        "-select_streams",
        "v:0",
        "-show_frames",
        "-show_entries",
        "frame=pts,duration",
    )
    packets = pk["packets"]
    pts = [int(p["pts"]) for p in packets]
    frame_lines = [f"{f.get('pts')},{f.get('duration')}" for f in fr["frames"]]
    return {
        "streams": info["streams"],
        "format": info["format"],
        "pts": pts,
        "packet_hashes": [p["data_hash"] for p in packets],
        "frame_pts_hash": hashlib.sha256("\n".join(frame_lines).encode()).hexdigest(),
        "moov_first": moov_before_mdat(path),
    }


def video_checks(probe: dict[str, Any], total_frames: int) -> list[Check]:
    """QM-060..063 + 077 on a silent 1080x1920 30 fps master (also used for mezzanines)."""
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
            and (v["width"], v["height"]) == (1080, 1920)
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
    deltas = pts_deltas(probe["pts"])
    bad = [d for d in deltas if d != TICKS]
    checks.append(
        Check(
            f"QM-061 packet PTS deltas all {TICKS} ticks (tb {v.get('time_base')})",
            v.get("time_base") == "1/30000" and not bad,
            f"{len(bad)} off, first {bad[:3]}",
        )
    )
    nb = int(v["nb_read_frames"])
    checks.append(
        Check("QM-062 nb_read_frames == plan", nb == total_frames, f"{nb} vs {total_frames}")
    )
    dur = float(probe["format"]["duration"])
    checks.append(
        Check(
            "QM-063 duration within 1 frame",
            abs(dur - total_frames * FRAME_S) <= FRAME_S + 1e-9,
            f"{dur:.6f} vs {total_frames * FRAME_S:.6f}",
        )
    )
    return checks


def verify_render(tools: Tools, plan: Plan, path: Path, palette: Rgb) -> dict[str, Any]:
    """Full per-render verification. ``expected`` is recomputed here from the beats with
    ``framemath`` (independent of the planner), and must also equal the plan's stored frames."""
    probe = probe_video(tools, path)
    checks = video_checks(probe, plan.total_frames)
    oracle = cut_frames(plan.beat_times, plan.t0, plan.fps, plan.lead)
    checks.append(Check("plan frames == framemath oracle", oracle == plan.frames))
    colours = decode_colours(tools, path)
    labels = [int(x) for x in nearest_labels(colours, palette)]
    # adjacent shots never share a clip, so every planned cut is an observable colour change
    detected = detected_changes(labels)
    cuts = compare_cuts(oracle[1:], detected)
    checks.append(Check("QM-064 every cut at its exact frame (0-frame error)", bool(cuts["pass"])))
    lengths = shot_lengths([*oracle, plan.total_frames])
    return {
        "pass": all(c.ok for c in checks),
        "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in checks],
        "cuts": cuts,
        "n_decoded_frames": len(labels),
        "detected_cut_frames": detected,
        "expected_cut_frames": oracle[1:],
        "shot_lengths": lengths,
        "frame_pts_hash": probe["frame_pts_hash"],
        "video_packet_hash": hashlib.sha256("".join(probe["packet_hashes"]).encode()).hexdigest(),
        "n_packets": len(probe["packet_hashes"]),
    }
