"""The audited FFmpeg/FFprobe runner (ARCH §11, SEC-010..012/015..017): the one process spawner.

* argument lists only: `shell=False`, an empty environment, its own process group;
* every ffmpeg call carries exactly one `-protocol_whitelist file` (no `pipe`);
* inputs get a forced `-f` chosen by the pure magic-byte sniff, never auto-detection;
* a string that looks like a joined command line is refused;
* a wall-clock timeout, a cancel request or an interrupt kills the whole process group.
"""

import contextlib
import hashlib
import json
import os
import re
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from saveclock.domain.audio_rules import AudioProbe, StreamInfo
from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.framemath import FPS
from saveclock.domain.video_checks import moov_before_mdat
from saveclock.domain.windows import Window

COMMON = ["-hide_banner", "-nostdin", "-loglevel", "error", "-protocol_whitelist", "file", "-y"]
PROBE_COMMON = ["-v", "error", "-hide_banner", "-protocol_whitelist", "file"]
PROBE_LIMITS = ["-probesize", "5000000", "-analyzeduration", "5000000"]
PROBE_ENTRIES = (
    "stream=codec_type,codec_name,profile,width,height,sample_rate,channels,duration"
    ":stream_disposition=attached_pic:format=duration,size,format_name"
)
PRLIMIT = Path("/usr/bin/prlimit")
LIMIT_AS_BYTES = 4 * 1024**3
LIMIT_CPU_S = 600
POLL_S = 0.5
CANCEL_POLL_S = 2.0  # the cancel check may open a database connection
PROBE_TIMEOUT_S = 60
CANONICALIZE_TIMEOUT_S = 120
STDERR_TAIL = 4096
_FORBIDDEN_OPTS = frozenset(
    {"-protocol_blacklist", "-safe", "-allowed_extensions", "-allowed_segment_extensions"}
    | {"-extension_picky", "-http_proxy", "-headers", "-user_agent"}
)
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_JOINED = re.compile(r"^-[A-Za-z_:0-9]+\s+\S")  # e.g. "-i file" or "-vf scale=1:1" in one string


class FfError(RuntimeError):
    """An ffmpeg/ffprobe call failed or was refused before running."""


class FfTimeout(FfError):
    """The wall-clock limit ran out; the process group was killed (transient)."""


class FfCanceled(FfError):
    """A cancel request killed the process group."""


class ProbeFailed(FfError):
    """ffprobe could not read the file: a non-zero exit or unreadable output (permanent)."""


class DecodeFailed(FfError):
    """The file did not decode cleanly: a non-zero exit or any stderr output (permanent)."""


@dataclass(frozen=True)
class Tools:
    ffmpeg: str
    ffprobe: str


@dataclass
class RunResult:
    returncode: int
    stdout: bytes
    stderr: str
    wall_s: float


def check_args(cmd: list[str]) -> None:
    """Refuse anything that is not a clean argument list."""
    if not cmd or not all(isinstance(a, str) for a in cmd):
        msg = "command must be a non-empty list of str"
        raise FfError(msg)
    if re.search(r"\s", cmd[0]) and not Path(cmd[0]).is_file():  # a checkout path may have spaces
        msg = f"executable contains whitespace (joined command line?): {cmd[0]!r}"
        raise FfError(msg)
    for a in cmd[1:]:
        if _JOINED.match(a) or re.match(r"^(\S*/)?(ffmpeg|ffprobe)\s", a):
            msg = f"argument looks like a joined command line: {a!r}"
            raise FfError(msg)
    name = Path(cmd[0]).name
    if "ffmpeg" in name and "-version" not in cmd and "-protocol_whitelist" not in cmd:
        msg = "ffmpeg call without -protocol_whitelist"
        raise FfError(msg)
    if name in ("ffmpeg", "ffprobe") or "-protocol_whitelist" in cmd:
        _check_protocol_options(cmd)


def _check_protocol_options(cmd: list[str]) -> None:
    """Refuse caller-supplied protocol/demuxer-safety options and URL-style inputs."""
    wl = [i for i, a in enumerate(cmd) if a == "-protocol_whitelist"]
    if len(wl) > 1 or (wl and (wl[0] + 1 >= len(cmd) or cmd[wl[0] + 1] != "file")):
        msg = "protocol whitelist must be exactly one '-protocol_whitelist file'"
        raise FfError(msg)
    for a in cmd[1:]:
        if a in _FORBIDDEN_OPTS:
            msg = f"caller-supplied option refused: {a}"
            raise FfError(msg)
    for i, a in enumerate(cmd[:-1]):
        if a == "-i" and _SCHEME.match(cmd[i + 1]) and not cmd[i + 1].startswith("file:"):
            msg = f"URL-style input refused: {cmd[i + 1]!r}"
            raise FfError(msg)


def ffmpeg_cmd(tools: Tools, *args: str) -> list[str]:
    return [tools.ffmpeg, *COMMON, *args]


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


def run(
    cmd: list[str],
    timeout: float,
    *,
    cancel: Callable[[], bool] | None = None,
    check: bool = True,
) -> RunResult:
    """Run an argument list: no shell, empty environment, own process group, 4 GB / 600 s limits."""
    check_args(cmd)
    argv = cmd
    if PRLIMIT.exists():
        argv = [str(PRLIMIT), f"--as={LIMIT_AS_BYTES}", f"--cpu={LIMIT_CPU_S}", "--", *cmd]
    started = last_cancel_check = time.monotonic()
    proc = subprocess.Popen(  # noqa: S603 - an audited argument list, never a shell
        argv,
        shell=False,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={},
    )
    try:
        while True:
            try:
                out, err = proc.communicate(timeout=POLL_S)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started > timeout:
                    _kill_group(proc)
                    msg = f"timeout after {timeout}s: {Path(cmd[0]).name}"
                    raise FfTimeout(msg) from None
                now = time.monotonic()
                if cancel is not None and now - last_cancel_check >= CANCEL_POLL_S:
                    last_cancel_check = now
                    if cancel():
                        _kill_group(proc)
                        msg = f"canceled: {Path(cmd[0]).name}"
                        raise FfCanceled(msg) from None
    except BaseException:
        if proc.poll() is None:
            _kill_group(proc)
        raise
    res = RunResult(
        proc.returncode, out, err.decode("utf-8", "replace"), time.monotonic() - started
    )
    if check and proc.returncode != 0:
        msg = f"exit {proc.returncode}: {Path(cmd[0]).name}\n{res.stderr[-STDERR_TAIL:]}"
        raise FfError(msg)
    return res


def _probe_json(tools: Tools, path: Path, fmt: str, *extra: str) -> dict[str, Any]:
    cmd = [tools.ffprobe, *PROBE_COMMON, "-f", fmt, *PROBE_LIMITS, "-print_format", "json"]
    try:
        data: dict[str, Any] = json.loads(run([*cmd, *extra, str(path)], PROBE_TIMEOUT_S).stdout)
    except (FfTimeout, FfCanceled):
        raise
    except (FfError, ValueError) as exc:
        msg = "ffprobe could not read the file"
        raise ProbeFailed(msg) from exc
    return data


def _attached_picture_bytes(tools: Tools, path: Path, fmt: str, index: int) -> int:
    data = _probe_json(
        tools, path, fmt, "-select_streams", str(index), "-show_entries", "packet=size"
    )
    return sum(int(p.get("size", 0)) for p in data.get("packets", []))


def _num(value: Any, kind: type[float] | type[int]) -> Any:  # noqa: ANN401
    try:
        return kind(value)
    except (TypeError, ValueError):
        return None


def probe_audio(tools: Tools, path: Path, fmt: str) -> AudioProbe:
    """ffprobe with a forced `-f`. Tags are never requested (P4-5)."""
    data = _probe_json(tools, path, fmt, "-show_entries", PROBE_ENTRIES)
    streams: list[StreamInfo] = []
    for index, s in enumerate(data.get("streams", [])):
        attached = bool(s.get("disposition", {}).get("attached_pic"))
        streams.append(
            StreamInfo(
                codec_type=str(s.get("codec_type", "")),
                codec_name=str(s.get("codec_name", "")),
                profile=s.get("profile"),
                sample_rate=_num(s.get("sample_rate"), int),
                channels=_num(s.get("channels"), int),
                attached_pic=attached,
                picture_bytes=_attached_picture_bytes(tools, path, fmt, index) if attached else 0,
            )
        )
    duration = _num(data.get("format", {}).get("duration"), float)
    return AudioProbe(str(data.get("format", {}).get("format_name", "")), duration, tuple(streams))


def canonicalize(
    tools: Tools,
    src: Path,
    fmt: str,
    out_flac: Path,
    *,
    cancel: Callable[[], bool] | None = None,
    timeout: float = CANONICALIZE_TIMEOUT_S,
) -> None:
    """Decode once to FLAC 48 kHz stereo with no tags (ARCH §11 Canonicalize, SEC-018)."""
    cmd = ffmpeg_cmd(
        tools,
        *("-f", fmt, "-i", str(src)),
        *("-map", "0:a:0", "-vn", "-sn", "-dn", "-map_metadata", "-1"),
        *("-c:a", "flac", "-ar", "48000", "-ac", "2", "-fflags", "+bitexact", str(out_flac)),
    )
    try:
        res = run(cmd, timeout, cancel=cancel, check=False)
    except FfError:
        out_flac.unlink(missing_ok=True)
        raise
    if res.returncode != 0 or res.stderr.strip():
        out_flac.unlink(missing_ok=True)
        msg = f"decode failed: {res.stderr[-STDERR_TAIL:]}"
        raise DecodeFailed(msg)


# --- stock clips: probe, sample, normalize to the mezzanine (ARCH §11, plan 005) ------------------

MP4_FMT = "mov,mp4,m4a,3gp,3g2,mj2"  # forced input format for every stock clip: never auto-detect
SAMPLE_TIMEOUT_S = 60
MEZZ_TIMEOUT_S = 120
SAMPLE_VF = "fps=1,scale=224:-2"
MEZZ_VF = (
    f"fps={FPS},scale=1080:1920:force_original_aspect_ratio=increase:flags=bicubic,"
    "crop=1080:1920,setsar=1,format=yuv420p"
)
# x264 only: the libopenh264 fallback of the spike is not ported
MEZZ_ENCODE = (
    *("-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-profile:v", "high"),
    *("-g", "15", "-keyint_min", "15", "-sc_threshold", "0", "-bf", "2"),
)
STOCK_ENTRIES = (
    "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,duration"
    ":stream_tags=rotate:stream_side_data=rotation:format=duration,size"
)
ROTATED = (90, 270)


@dataclass(frozen=True)
class StockProbe:
    width: int  # as displayed (rotation applied)
    height: int
    duration_s: float
    fps: float | None
    size_bytes: int | None


def _fraction(value: Any) -> float | None:  # noqa: ANN401
    try:
        num, den = str(value).split("/")
        return float(num) / float(den) if float(den) else None
    except (ValueError, ZeroDivisionError):
        return None


def probe_stock(tools: Tools, path: Path) -> StockProbe:
    """ffprobe of a downloaded clip with a forced mp4-family `-f`. Exactly one video stream
    (audio is ignored later by `-map 0:v:0`); displayed size accounts for a rotation flag."""
    data = _probe_json(tools, path, MP4_FMT, "-show_entries", STOCK_ENTRIES)
    videos = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if len(videos) != 1:
        msg = "expected exactly one video stream"
        raise ProbeFailed(msg)
    v = videos[0]
    width, height = _num(v.get("width"), int), _num(v.get("height"), int)
    duration = _num(v.get("duration"), float) or _num(data.get("format", {}).get("duration"), float)
    if not width or not height or not duration:
        msg = "video stream has no size or duration"
        raise ProbeFailed(msg)
    rotation = _num(v.get("tags", {}).get("rotate"), int)
    for side in v.get("side_data_list", []):
        rotation = _num(side.get("rotation"), float) if "rotation" in side else rotation
    if rotation is not None and abs(int(rotation)) % 360 in ROTATED:
        width, height = height, width
    return StockProbe(
        width,
        height,
        float(duration),
        _fraction(v.get("avg_frame_rate")) or _fraction(v.get("r_frame_rate")),
        _num(data.get("format", {}).get("size"), int),
    )


def sample_frames(
    tools: Tools,
    src: Path,
    out_dir: Path,
    start_s: float,
    n: int = 8,
    *,
    cancel: Callable[[], bool] | None = None,
) -> list[Path]:
    """`n` frames (one per second from `start_s`), 224 px wide. `-ss` is an output option, which
    is slower than an input seek but frame accurate."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%02d.jpg"
    cmd = ffmpeg_cmd(
        tools,
        *("-f", MP4_FMT, "-i", str(src)),
        *("-map", "0:v:0", "-an", "-sn", "-dn", "-ss", f"{start_s}"),
        *("-vf", SAMPLE_VF, "-frames:v", str(n), str(pattern)),
    )
    run(cmd, SAMPLE_TIMEOUT_S, cancel=cancel)
    return sorted(out_dir.glob("frame_*.jpg"))


def mezz_cmd(tools: Tools, src: Path, window: Window, out: Path) -> list[str]:
    """The mezzanine template (ARCH §11 Normalize): 1080x1920, 30 fps CFR, x264 High, GOP 15."""
    return ffmpeg_cmd(
        tools,
        *("-f", MP4_FMT, "-i", str(src)),
        *("-map", "0:v:0", "-an", "-sn", "-dn"),
        *("-ss", f"{window.start_s}", "-t", f"{window.len_s}"),
        *("-vf", MEZZ_VF),
        *("-r", str(FPS), "-fps_mode", "cfr"),
        *MEZZ_ENCODE,
        *("-video_track_timescale", "30000", "-movflags", "+faststart", str(out)),
    )


def build_mezz(
    tools: Tools,
    src: Path,
    window: Window,
    out: Path,
    *,
    cancel: Callable[[], bool] | None = None,
    timeout: float = MEZZ_TIMEOUT_S,
) -> None:
    try:
        run(mezz_cmd(tools, src, window, out), timeout, cancel=cancel)
    except FfError:
        out.unlink(missing_ok=True)
        raise


def probe_video(tools: Tools, path: Path, *, hashes: bool = False) -> dict[str, Any]:
    """Everything `domain.video_checks.video_checks` needs: streams, format, packet PTS values,
    the decoded frame count and whether `moov` precedes `mdat`. `hashes=True` (the master check
    and Mode A) adds the sha256 of every video packet (`packet_hashes`, QM-087) and a hash of the
    frame PTS and durations (`frame_pts_hash`); the mezzanine check does not pay for them."""
    info = _probe_json(
        tools,
        path,
        MP4_FMT,
        *("-count_frames", "-show_format", "-show_streams"),
        *(
            "-show_entries",
            "stream=codec_type,codec_name,profile,pix_fmt,width,height,sample_aspect_ratio,"
            "r_frame_rate,avg_frame_rate,time_base,nb_read_frames,start_time"
            ":format=duration,format_name,nb_streams",
        ),
    )
    packets = _probe_json(
        tools,
        path,
        MP4_FMT,
        *("-select_streams", "v:0", "-show_packets"),
        *(("-show_data_hash", "sha256") if hashes else ()),
        *("-show_entries", "packet=pts,dts,duration,flags" + (",data_hash" if hashes else "")),
    )["packets"]
    out: dict[str, Any] = {
        "streams": info["streams"],
        "format": info["format"],
        "pts": [int(p["pts"]) for p in packets],
        "moov_first": moov_before_mdat(path),
    }
    if hashes:
        frames = _probe_json(
            tools,
            path,
            MP4_FMT,
            *("-select_streams", "v:0", "-show_frames", "-show_entries", "frame=pts,duration"),
        )["frames"]
        lines = "\n".join(f"{f.get('pts')},{f.get('duration')}" for f in frames)
        out["packet_hashes"] = [p["data_hash"] for p in packets]
        out["frame_pts_hash"] = hashlib.sha256(lines.encode()).hexdigest()
    return out


# --- the final render and the Mode A remux (ARCH §11, plan 007) --------------------------------

# shortcut: the encode is this template, `plan.output.crf/preset` are not read; upgrade when the
# plan's output block becomes owner-editable
RENDER_ENCODE = (
    *("-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high"),
    *("-pix_fmt", "yuv420p"),
)
MAX_RENDER_INPUTS = 60  # the planner never makes more cuts than this (plan 006's validator)
AAC_TRANSCODE = ("-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2")


def filter_graph(plan: EditPlan) -> str:
    """trim by FRAME index (never seconds), concat, null: ARCH §11 final-render template."""
    parts: list[str] = []
    for k, cut in enumerate(plan.cuts):
        start = cut.clip.in_frame
        end = start + (cut.out_end_frame - cut.out_start_frame)
        parts.append(f"[{k}:v]trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS[v{k}]")
    labels = "".join(f"[v{k}]" for k in range(len(plan.cuts)))
    parts.append(f"{labels}concat=n={len(plan.cuts)}:v=1:a=0[vc]")
    parts.append("[vc]null[vout]")
    return ";".join(parts)


def render_cmd(
    tools: Tools,
    plan: EditPlan,
    mezz_paths: Sequence[Path],
    out: Path,
    *,
    progress: Path,
    threads: int,
) -> list[str]:
    """One `-i` per cut (in plan order): the silent master in one pass, no audio."""
    if not 1 <= len(plan.cuts) <= MAX_RENDER_INPUTS or len(mezz_paths) != len(plan.cuts):
        msg = f"a render takes 1 to {MAX_RENDER_INPUTS} cuts, one mezzanine each"
        raise FfError(msg)
    inputs = [a for path in mezz_paths for a in ("-f", MP4_FMT, "-i", str(path))]
    return ffmpeg_cmd(
        tools,
        *inputs,
        *("-filter_complex", filter_graph(plan)),
        *("-map", "[vout]", "-an"),
        *RENDER_ENCODE,
        *("-r", str(FPS), "-fps_mode", "cfr", "-g", "60", "-video_track_timescale", "30000"),
        *("-threads", str(threads)),
        *("-frames:v", str(plan.total_frames)),
        *("-progress", str(progress), "-nostats"),
        *("-movflags", "+faststart", "-f", "mp4", str(out)),
    )


def remux_cmd(
    tools: Tools,
    master: Path,
    source: Path,
    source_fmt: str,
    *,
    audio_start_s: float,
    total_frames: int,
    out: Path,
    aac_copy: bool,
) -> list[str]:
    """Mode A (ARCH §11): the master's video copied, the song trimmed in. No gain, loudness, EQ or
    filter: the audio is stream-copied when it is AAC-LC and encoded to AAC-LC once otherwise."""
    dur = f"{total_frames / FPS:.6f}"
    audio = ("-c:a", "copy") if aac_copy else AAC_TRANSCODE
    return ffmpeg_cmd(
        tools,
        *("-f", MP4_FMT, "-i", str(master)),
        *("-ss", f"{audio_start_s:.6f}", "-t", dur, "-f", source_fmt, "-i", str(source)),
        *("-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", *audio),
        *("-t", dur, "-movflags", "+faststart", "-f", "mp4", str(out)),
    )


def parse_progress(text: str) -> tuple[int, bool]:
    """FFmpeg's `-progress` file: `key=value` blocks ending in `progress=continue|end`. The last
    frame count and whether the run has ended."""
    frame, ended = 0, False
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key == "frame" and value.strip().isdigit():
            frame = int(value)
        elif key == "progress":
            ended = value.strip() == "end"
    return frame, ended


class ProgressTail:
    """Polls the `-progress` file in a thread and reports `frame / total` (callback throttles)."""

    def __init__(
        self,
        path: Path,
        total_frames: int,
        callback: Callable[[float], None],
        *,
        poll_s: float = 0.5,
    ) -> None:
        self._path, self._total, self._callback, self._poll = path, total_frames, callback, poll_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="progress-tail")

    def _read(self) -> bool:
        try:
            frame, ended = parse_progress(self._path.read_text())
        except OSError:
            return False
        self._callback(min(1.0, frame / self._total))
        return ended

    def _run(self) -> None:
        while not self._stop.wait(self._poll):
            if self._read():
                return

    def __enter__(self) -> "ProgressTail":
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
