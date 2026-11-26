"""The measurements behind the per-render verification (QUALITY §7): the decode to null, the gray
frames, the black/frozen/loudness/silence filters and the Mode A probes.

Every call goes through the audited runner (`run`, argument lists, `-protocol_whitelist file`, a
forced `-f`, an empty environment). The filter checks print to stderr at log level `info`, and
`COMMON` sets `error`: a later `-loglevel info` wins, so only those calls parse stderr.
These functions measure and parse; `domain/verify.py` decides.
"""

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from saveclock.adapters.dsp import XCORR_SR
from saveclock.adapters.ffmpeg import (
    MP4_FMT,
    Tools,
    _probe_json,
    ffmpeg_cmd,
    probe_video,
    run,
)
from saveclock.domain.framemath import FPS

GRAY_W, GRAY_H = 96, 170  # QUALITY §7 (P7-1)
DECODE_TIMEOUT_S = 120
FILTER_TIMEOUT_S = 120
AUDIO_TIMEOUT_S = 60
BLACK_VF = "blackdetect=d=0.066:pic_th=0.98:pix_th=0.10"
FREEZE_VF = "freezedetect=n=-60dB:d=0.5"
SILENCE_AF = "silencedetect=n=-50dB:d=2"
MAX_GRAY_FRAMES = 2400  # 80 s at 30 fps: more is not a render this product makes

_BLACK = re.compile(r"black_duration:\s*([0-9.]+)")
_FREEZE_START = re.compile(r"freeze_start:\s*([0-9.]+)")
_FREEZE_DURATION = re.compile(r"freeze_duration:\s*([0-9.]+)")
_SILENCE_START = re.compile(r"silence_start:\s*(-?[0-9.]+)")
_SILENCE_DURATION = re.compile(r"silence_duration:\s*([0-9.]+)")
_LUFS = re.compile(r"^\s*I:\s*(-?[0-9.]+) LUFS", re.MULTILINE)
_TRUE_PEAK = re.compile(r"^\s*Peak:\s*(-?[0-9.]+) dBFS", re.MULTILINE)


def probe_master(tools: Tools, path: Path) -> dict[str, Any]:
    """`probe_video` with the packet and frame hashes (QM-087, the frame-PTS record)."""
    return probe_video(tools, path, hashes=True)


def decode_null(tools: Tools, path: Path) -> str:
    """QM-075: decode every frame to nothing; the returned text is what ffmpeg complained about
    (empty = playable). A non-zero exit with no message still counts as a complaint."""
    cmd = ffmpeg_cmd(tools, "-f", MP4_FMT, "-i", str(path), "-map", "0:v:0", "-f", "null", "-")
    res = run(cmd, DECODE_TIMEOUT_S, check=False)
    text = res.stderr.strip()
    return text or (f"exit {res.returncode}" if res.returncode else "")


def decode_gray(
    tools: Tools, path: Path, w: int = GRAY_W, h: int = GRAY_H
) -> npt.NDArray[np.uint8]:
    """Every frame at `w` x `h`, gray, as `(n, h, w)` read from ffmpeg's stdout (an output pipe is
    not an input protocol, so `-protocol_whitelist file` stands). 96x170x1800 frames is 29 MB."""
    cmd = ffmpeg_cmd(
        tools,
        *("-f", MP4_FMT, "-i", str(path), "-map", "0:v:0"),
        *("-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"),
    )
    raw = run(cmd, DECODE_TIMEOUT_S).stdout
    frames = np.frombuffer(raw, dtype=np.uint8)
    return frames.reshape(-1, h, w)[:MAX_GRAY_FRAMES]


def parse_black(stderr: str) -> list[int]:
    """Durations of the black runs, in frames."""
    return [round(float(d) * FPS) for d in _BLACK.findall(stderr)]


def parse_freeze(stderr: str, total_s: float) -> list[float]:
    """Durations (s) of the frozen runs; a freeze that lasts to the end of the file has a start
    but no duration line."""
    starts = [float(s) for s in _FREEZE_START.findall(stderr)]
    durations = [float(d) for d in _FREEZE_DURATION.findall(stderr)]
    if len(starts) > len(durations):  # the last one ran to the end of the stream
        durations.append(max(0.0, total_s - starts[-1]))
    return durations


def parse_silence(stderr: str, total_s: float) -> list[float]:
    starts = [float(s) for s in _SILENCE_START.findall(stderr)]
    durations = [float(d) for d in _SILENCE_DURATION.findall(stderr)]
    if len(starts) > len(durations):
        durations.append(max(0.0, total_s - max(starts[-1], 0.0)))
    return durations


def parse_loudness(stderr: str) -> tuple[float | None, float | None]:
    """`(integrated LUFS, true peak dBTP)` from the ebur128 summary (the last block)."""
    lufs, peak = _LUFS.findall(stderr), _TRUE_PEAK.findall(stderr)
    return (float(lufs[-1]) if lufs else None, float(peak[-1]) if peak else None)


def _filter_stderr(tools: Tools, path: Path, vf: str) -> str:
    cmd = ffmpeg_cmd(
        tools,
        *("-loglevel", "info", "-f", MP4_FMT, "-i", str(path)),
        *("-map", "0:v:0", "-vf", vf, "-an", "-f", "null", "-"),
    )
    return run(cmd, FILTER_TIMEOUT_S).stderr


def blackdetect(tools: Tools, path: Path) -> list[int]:
    """QM-070: black runs of 2 frames or more, as frame counts."""
    return parse_black(_filter_stderr(tools, path, BLACK_VF))


def freezedetect(tools: Tools, path: Path, total_s: float) -> list[float]:
    """QM-071: runs of 0.5 s or more with no change, in seconds."""
    return parse_freeze(_filter_stderr(tools, path, FREEZE_VF), total_s)


def _audio_stderr(
    tools: Tools, path: Path, fmt: str, af: str, *, start_s: float | None, dur_s: float | None
) -> str:
    window = [
        *(("-ss", f"{start_s:.6f}") if start_s is not None else ()),
        *(("-t", f"{dur_s:.6f}") if dur_s is not None else ()),
    ]
    cmd = ffmpeg_cmd(
        tools,
        *("-loglevel", "info", *window, "-f", fmt, "-i", str(path)),
        *("-map", "0:a:0", "-af", af, "-vn", "-f", "null", "-"),
    )
    return run(cmd, AUDIO_TIMEOUT_S).stderr


def ebur128(
    tools: Tools,
    path: Path,
    fmt: str = MP4_FMT,
    start_s: float | None = None,
    dur_s: float | None = None,
) -> tuple[float | None, float | None]:
    """QM-073: integrated loudness (LUFS) and true peak (dBTP). Measured only, never applied."""
    return parse_loudness(
        _audio_stderr(tools, path, fmt, "ebur128=peak=true", start_s=start_s, dur_s=dur_s)
    )


def silencedetect(
    tools: Tools,
    path: Path,
    fmt: str = MP4_FMT,
    *,
    start_s: float | None = None,
    dur_s: float | None = None,
    total_s: float = 0.0,
) -> list[float]:
    """QM-074: digital silences of 2 s or more, in seconds."""
    return parse_silence(
        _audio_stderr(tools, path, fmt, SILENCE_AF, start_s=start_s, dur_s=dur_s),
        total_s or (dur_s or 0.0),
    )


def decode_mono8k(
    tools: Tools,
    path: Path,
    fmt: str,
    start_s: float | None = None,
    dur_s: float | None = None,
) -> npt.NDArray[np.float64]:
    """8 kHz mono float samples; `-ss`/`-t` are input options on the forced-format file."""
    sel = [
        *(("-ss", f"{start_s:.6f}") if start_s is not None else ()),
        *(("-t", f"{dur_s:.6f}") if dur_s is not None else ()),
    ]
    cmd = ffmpeg_cmd(
        tools,
        *sel,
        *("-f", fmt, "-i", str(path)),
        *("-map", "0:a:0", "-ac", "1", "-ar", str(XCORR_SR), "-f", "f32le", "-"),
    )
    return np.frombuffer(run(cmd, DECODE_TIMEOUT_S).stdout, dtype=np.float32).astype(np.float64)


def probe_remux(tools: Tools, path: Path) -> dict[str, Any]:
    """The remuxed file: its streams, and the sha256 of every video and audio packet."""
    info = _probe_json(
        tools,
        path,
        MP4_FMT,
        "-show_streams",
        *(
            "-show_entries",
            "stream=codec_type,codec_name,profile,sample_rate,channels,start_time,duration",
        ),
    )
    return {
        "streams": info["streams"],
        "video_hashes": packet_hashes(tools, path, MP4_FMT, "v:0"),
        "audio_hashes": packet_hashes(tools, path, MP4_FMT, "a:0"),
    }


def packet_hashes(tools: Tools, path: Path, fmt: str, stream: str) -> list[str]:
    data = _probe_json(
        tools,
        path,
        fmt,
        *("-select_streams", stream, "-show_packets", "-show_data_hash", "sha256"),
        *("-show_entries", "packet=data_hash"),
    )
    return [p["data_hash"] for p in data["packets"]]


def find_run(haystack: Sequence[str], needle: Sequence[str]) -> int | None:
    """Index where `needle` occurs as one contiguous run in `haystack`."""
    n = len(needle)
    if n == 0:
        return None
    for j in range(len(haystack) - n + 1):
        if haystack[j] == needle[0] and list(haystack[j : j + n]) == list(needle):
            return j
    return None
