"""The audited FFmpeg/FFprobe runner (ARCH §11, SEC-010..012/015..017): the one process spawner.

* argument lists only: `shell=False`, an empty environment, its own process group;
* every ffmpeg call carries exactly one `-protocol_whitelist file` (no `pipe`);
* inputs get a forced `-f` chosen by the pure magic-byte sniff, never auto-detection;
* a string that looks like a joined command line is refused;
* a wall-clock timeout, a cancel request or an interrupt kills the whole process group.
"""

import contextlib
import json
import os
import re
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from saveclock.domain.audio_rules import AudioProbe, StreamInfo

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
