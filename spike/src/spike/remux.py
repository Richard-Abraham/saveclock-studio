"""Mode A remux (ARCHITECTURE 11 "Mode A remux"; G0-12, QM-067/068/087)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from spike.ffwrap import MP4_FMT, RunResult, Tools, ffmpeg_cmd, probe_json, run, sniff_format
from spike.framemath import FPS

AAC_FRAME_S = 1024 / 48000  # 21.333 ms
OFFSET_LIMIT_S = 1 / 30  # 33.3 ms
SR = 8000
FloatArray = npt.NDArray[np.float64]


def remux_cmd(
    tools: Tools,
    master: Path,
    source: Path,
    audio_start_s: float,
    total_frames: int,
    out: Path,
    aac_copy: bool,
) -> list[str]:
    dur = f"{total_frames / FPS:.6f}"
    audio_codec = (
        ["-c:v", "copy", "-c:a", "copy"]
        if aac_copy
        else ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    )
    return ffmpeg_cmd(
        tools,
        *("-f", MP4_FMT, "-i", str(master)),
        *("-ss", f"{audio_start_s:.6f}", "-t", dur, "-f", sniff_format(source), "-i", str(source)),
        *("-map", "0:v:0", "-map", "1:a:0", *audio_codec),
        *("-t", dur, "-movflags", "+faststart", "-f", "mp4", str(out)),
    )


def is_aac_lc(tools: Tools, source: Path) -> bool:
    info = probe_json(tools, source, "-show_streams", "-select_streams", "a:0")
    s = info["streams"][0]
    return bool(s["codec_name"] == "aac" and s.get("profile") == "LC")


def build_remux(
    tools: Tools,
    master: Path,
    source: Path,
    audio_start_s: float,
    total_frames: int,
    out: Path,
    aac_copy: bool,
) -> RunResult:
    cmd = remux_cmd(tools, master, source, audio_start_s, total_frames, out, aac_copy)
    return run(cmd, 120, rss=True)


# ---- measurement --------------------------------------------------------------------------


def onset_envelope(x: FloatArray, sr: int = SR) -> FloatArray:
    """Rectify, 4 ms boxcar, half-wave-rectified first difference."""
    k = max(1, int(0.004 * sr))
    env = np.convolve(np.abs(x), np.ones(k) / k, mode="same")
    d = np.diff(env, prepend=env[0])
    return np.maximum(d, 0.0)


def parabolic_peak(y: FloatArray, k: int) -> float:
    if k <= 0 or k >= len(y) - 1:
        return float(k)
    y0, y1, y2 = y[k - 1], y[k], y[k + 1]
    denom = y0 - 2 * y1 + y2
    return float(k) if denom == 0 else float(k + 0.5 * (y0 - y2) / denom)


def xcorr_offset(ref: FloatArray, test: FloatArray, sr: int = SR, max_lag_s: float = 0.2) -> float:
    """Offset (s) of ``test`` relative to ``ref`` (positive = test is late). FFT cross-correlation
    of onset envelopes, parabolic peak refinement."""
    n = min(len(ref), len(test))
    a, b = onset_envelope(ref[:n], sr), onset_envelope(test[:n], sr)
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    c = np.fft.irfft(np.fft.rfft(b, nfft) * np.conj(np.fft.rfft(a, nfft)), nfft)
    c = np.concatenate([c[-(n - 1) :], c[:n]])  # lags -(n-1)..(n-1)
    zero = n - 1
    m = int(max_lag_s * sr)
    seg = c[zero - m : zero + m + 1]
    k = int(np.argmax(seg))
    return (parabolic_peak(seg, k) - m) / sr


def decode_mono8k(
    tools: Tools, path: Path, start_s: float | None = None, dur_s: float | None = None
) -> FloatArray:
    """Decode to 8 kHz mono float32 (``-ss/-t`` as input options on the forced-format source)."""
    sel: list[str] = []
    if start_s is not None:
        sel += ["-ss", f"{start_s:.6f}"]
    if dur_s is not None:
        sel += ["-t", f"{dur_s:.6f}"]
    cmd = ffmpeg_cmd(
        tools,
        *sel,
        *("-f", sniff_format(path), "-i", str(path)),
        *("-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"),
    )
    return np.frombuffer(run(cmd, 120).stdout, dtype=np.float32).astype(np.float64)


def audio_packets(tools: Tools, path: Path) -> dict[str, Any]:
    pk = probe_json(
        tools,
        path,
        "-select_streams",
        "a:0",
        "-show_packets",
        "-show_data_hash",
        "sha256",
        "-show_entries",
        "packet=pts,duration,size,data_hash",
    )
    return {"hashes": [p["data_hash"] for p in pk["packets"]], "packets": pk["packets"]}


def find_run(haystack: Sequence[str], needle: Sequence[str]) -> int | None:
    """Index where ``needle`` occurs as a contiguous run in ``haystack``."""
    n = len(needle)
    if n == 0:
        return None
    for j in range(len(haystack) - n + 1):
        if haystack[j] == needle[0] and list(haystack[j : j + n]) == list(needle):
            return j
    return None


def verify_remux(
    tools: Tools,
    master_video_hashes: Sequence[str],
    master_pts: Sequence[int],
    remux_path: Path,
    source: Path,
    audio_start_s: float,
    total_frames: int,
    aac_copy: bool,
) -> dict[str, Any]:
    """QM-067/068/087 + QM-077 (Mode A: 1 video + 1 audio)."""
    dur = total_frames / FPS
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    info = probe_json(
        tools,
        remux_path,
        "-show_streams",
        "-show_entries",
        "stream=codec_type,codec_name,profile,sample_rate,channels,start_time,duration",
    )
    kinds = sorted(s["codec_type"] for s in info["streams"])
    add("QM-077 exactly 1 video + 1 audio", kinds == ["audio", "video"], str(kinds))
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    add(
        "audio is AAC-LC",
        a["codec_name"] == "aac" and a.get("profile") == "LC",
        str(a.get("profile")),
    )
    if not aac_copy:
        add("transcoded audio is 48 kHz", a["sample_rate"] == "48000", a["sample_rate"])

    # video: bit-identical packets (QM-087)
    vp = probe_json(
        tools,
        remux_path,
        "-select_streams",
        "v:0",
        "-show_packets",
        "-show_data_hash",
        "sha256",
        "-show_entries",
        "packet=pts,data_hash",
    )["packets"]
    r_hashes = [p["data_hash"] for p in vp]
    r_pts = [int(p["pts"]) for p in vp]
    add(
        "QM-087 video packets bit-identical to master",
        r_hashes == list(master_video_hashes),
        f"{len(r_hashes)} vs {len(master_video_hashes)}",
    )
    pts_shift = sorted({p - m for p, m in zip(r_pts, master_pts, strict=False)})
    video_hash = hashlib.sha256("".join(r_hashes).encode()).hexdigest()

    # audio packets
    ap = audio_packets(tools, remux_path)
    copy_info: dict[str, Any] = {}
    if aac_copy:
        sp = audio_packets(tools, source)
        j = find_run(sp["hashes"], ap["hashes"])
        add(
            "QM-087 AAC-LC audio packets == source packets (stream copy)",
            j is not None,
            f"run at source packet {j} of {len(sp['hashes'])}, {len(ap['hashes'])} packets",
        )
        copy_info = {"source_packet_offset": j, "n_packets": len(ap["hashes"])}

    # decode and measure offset/drift/duration
    got = decode_mono8k(tools, remux_path)
    ref = decode_mono8k(tools, source, audio_start_s, dur)
    audio_dur = len(got) / SR
    add(
        "audio duration within 1 AAC frame (21.3 ms)",
        abs(audio_dur - dur) <= AAC_FRAME_S + 1e-3,
        f"{audio_dur:.4f} vs {dur:.4f}",
    )
    w = int(2.0 * SR)
    n = min(len(got), len(ref))
    off0 = xcorr_offset(ref[:w], got[:w])
    off1 = xcorr_offset(ref[n - w : n], got[n - w : n])
    drift = off1 - off0
    drift_per_60 = drift * (60.0 / max(dur - 2.0, 1.0))
    add("QM-067 |offset| <= 33.3 ms at t~1 s", abs(off0) <= OFFSET_LIMIT_S, f"{off0 * 1e3:.2f} ms")
    add(
        "QM-067 |offset| <= 33.3 ms at t~dur-1 s",
        abs(off1) <= OFFSET_LIMIT_S,
        f"{off1 * 1e3:.2f} ms",
    )
    add(
        "QM-068 drift <= 33.3 ms / 60 s",
        abs(drift_per_60) <= OFFSET_LIMIT_S,
        f"{drift * 1e3:.2f} ms over {dur - 2.0:.0f} s",
    )
    return {
        "pass": all(c["ok"] for c in checks),
        "checks": checks,
        "aac_copy": aac_copy,
        "offset_start_ms": off0 * 1e3,
        "offset_end_ms": off1 * 1e3,
        "drift_ms": drift * 1e3,
        "audio_duration_s": audio_dur,
        "video_start_time": v.get("start_time"),
        "audio_start_time": a.get("start_time"),
        "video_pts_shift_vs_master": pts_shift[:3],
        "video_packet_hash": video_hash,
        "audio_codec": f"{a['codec_name']}/{a.get('profile')}/{a['sample_rate']}Hz/{a['channels']}ch",
        **copy_info,
    }
