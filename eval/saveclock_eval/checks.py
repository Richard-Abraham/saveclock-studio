"""Per-render checks that the render's own `verify` summary cannot show (plan 009, Step 7).

Each check is independent of the service: the host `ffprobe` and `ffmpeg` re-probe the downloaded
files, the frame rule is recomputed in exact arithmetic (`fractions.Fraction`), and PySceneDetect
re-runs on the downloaded silent master. A check returns `Check(id, ok, detail)`; nothing here
talks to the API.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

FPS = 30
WIDTH, HEIGHT = 1080, 1920
CUT_TOLERANCE_FRAMES = 1  # QM-064 / QM-036(a): within one frame of a planned cut


@dataclass(frozen=True)
class Check:
    id: str  # the QM id it speaks for, with a suffix when one id has several parts
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- the frame rule, in exact arithmetic ---------------------------------------------------
def frame_rule(t_s: Fraction, t0_s: Fraction, lead_frames: int, fps: int = FPS) -> int:
    """QUALITY section 2: cut frame = floor((t - t0) * fps + 1/2) - lead_frames, exactly.

    `round()` is wrong here: Python rounds half to even, and 128 BPM puts a beat exactly on a
    half frame (beat 8 at 3.75 s = 112.5 frames, which the rule sends to 113).
    """
    return math.floor((t_s - t0_s) * fps + Fraction(1, 2)) - lead_frames


def check_cut_frames(plan: dict[str, Any]) -> Check:
    """Every planned cut's `out_start_frame` equals the frame rule applied to its own beat time."""
    t0 = Fraction(plan["segment"]["start_s"])
    lead = int(plan["lead_frames"])
    bad = []
    for cut in plan["cuts"]:
        want = frame_rule(Fraction(cut["beat_ref"]["t_s"]), t0, lead)
        if cut["out_start_frame"] != want:
            bad.append((cut["index"], cut["out_start_frame"], want))
    if bad:
        i, got, want = bad[0]
        return Check("QM-064/oracle", False, f"{len(bad)} cut(s) off the frame rule; first: cut {i} is {got}, rule says {want}")
    return Check("QM-064/oracle", True, f"{len(plan['cuts'])} cuts follow the frame rule")


# --- QM-038 -----------------------------------------------------------------------------
def check_no_repeats(plan: dict[str, Any], flags: dict[str, Any]) -> Check:
    """The same stock clip id is not used twice in one video, unless the pool was exhausted."""
    seen: dict[tuple[str, str], int] = {}
    repeats = []
    for cut in plan["cuts"]:
        key = (cut["clip"]["provider"], cut["clip"]["provider_id"])
        if key in seen:
            repeats.append(key)
        seen[key] = cut["index"]
    if repeats and flags.get("pool_exhausted"):
        return Check("QM-038", True, f"{len(repeats)} repeat(s), allowed: the pool was exhausted")
    return Check("QM-038", not repeats, f"repeated clips: {repeats[:3]}" if repeats else f"{len(seen)} distinct clips")


# --- ffprobe / ffmpeg --------------------------------------------------------------------
def ffprobe_json(ffprobe: str, path: Path) -> dict[str, Any]:
    out = subprocess.run(  # noqa: S603 - a fixed argument list on a file the eval wrote
        [ffprobe, "-v", "error", "-protocol_whitelist", "file", "-count_frames", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True, timeout=300,
    )
    probed: dict[str, Any] = json.loads(out.stdout)
    return probed


def moov_first(path: Path) -> bool:
    """`+faststart`: the `moov` box comes before `mdat` among the top-level boxes."""
    with path.open("rb") as fh:
        while header := fh.read(8):
            if len(header) < 8:  # noqa: PLR2004
                return False
            size, kind = struct.unpack(">I4s", header)
            if kind == b"moov":
                return True
            if kind == b"mdat":
                return False
            if size == 1:
                size = struct.unpack(">Q", fh.read(8))[0]
                fh.seek(size - 16, 1)
            elif size == 0:
                return False
            else:
                fh.seek(size - 8, 1)
    return False


def check_probe(probe: dict[str, Any], path: Path, total_frames: int, *, with_audio: bool) -> list[Check]:
    """QM-060 to QM-063 on the downloaded file, by the host ffprobe."""
    streams = probe["streams"]
    video = [s for s in streams if s["codec_type"] == "video"]
    audio = [s for s in streams if s["codec_type"] == "audio"]
    problems: list[str] = []
    if len(video) != 1:
        problems.append(f"{len(video)} video streams")
    if len(audio) != (1 if with_audio else 0):
        problems.append(f"{len(audio)} audio streams, want {1 if with_audio else 0}")
    if video:
        v = video[0]
        want = {"codec_name": "h264", "profile": "High", "pix_fmt": "yuv420p", "width": WIDTH, "height": HEIGHT,
                "r_frame_rate": "30/1", "avg_frame_rate": "30/1"}
        problems += [f"{k}={v.get(k)!r} (want {w!r})" for k, w in want.items() if v.get(k) != w]
        if v.get("sample_aspect_ratio") not in (None, "1:1", "N/A"):
            problems.append(f"sar={v.get('sample_aspect_ratio')}")
        if int(v.get("nb_read_frames", -1)) != total_frames:
            problems.append(f"{v.get('nb_read_frames')} frames, plan says {total_frames}")
    if audio and with_audio and (audio[0].get("codec_name"), audio[0].get("profile")) != ("aac", "LC"):
        problems.append(f"audio is {audio[0].get('codec_name')}/{audio[0].get('profile')}, want aac/LC")
    if not moov_first(path):
        problems.append("moov is not before mdat (no +faststart)")
    label = "mode_a" if with_audio else "master"
    return [Check(f"QM-060..063/{label}", not problems, "; ".join(problems) or "layout, 1080x1920, 30/1, frame count, moov first")]


def video_packets_md5(ffmpeg: str, path: Path) -> str:
    """The md5 of the first video stream's packets, copied (no decode, no re-encode)."""
    out = subprocess.run(  # noqa: S603 - a fixed argument list on a file the eval wrote
        [ffmpeg, "-v", "error", "-protocol_whitelist", "file", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"],
        capture_output=True, text=True, check=True, timeout=300,
    )
    return out.stdout.strip()


def check_mode_a_integrity(ffmpeg: str, master: Path, mode_a: Path) -> Check:
    """QM-087: the video stream of the Mode A file is a bit-exact copy of the silent master."""
    a, b = video_packets_md5(ffmpeg, master), video_packets_md5(ffmpeg, mode_a)
    return Check("QM-087", a == b, "video packets equal" if a == b else f"video packets differ: {a[:20]} vs {b[:20]}")


# --- QM-036(a): the detector on the downloaded master --------------------------------------
def check_detected_cuts(detected_frames: list[int], plan: dict[str, Any]) -> Check:
    """No detected cut is farther than one frame from a planned cut (QM-036(a), P9-15)."""
    planned = [c["out_start_frame"] for c in plan["cuts"][1:]]
    stray = [f for f in detected_frames if not any(abs(f - p) <= CUT_TOLERANCE_FRAMES for p in planned)]
    return Check("QM-036(a)", not stray, f"{len(stray)} detected cut(s) not on a planned cut: {stray[:5]}" if stray else f"{len(detected_frames)} detected, all on planned cuts")


def detect_cuts(path: Path) -> list[int]:
    """Frame numbers where PySceneDetect's content detector sees a cut (the same idea as QM-066)."""
    from scenedetect import ContentDetector, detect  # the dev group; never an image dependency

    scenes = detect(str(path), ContentDetector())
    return [int(start.get_frames()) for start, _end in scenes[1:]]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()
