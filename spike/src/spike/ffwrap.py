"""Argument-list-only FFmpeg/FFprobe runner (ARCHITECTURE 11 hardening, SEC-010/011).

* every call is ``subprocess.run([...], shell=False, timeout=...)``;
* every ffmpeg call carries ``-protocol_whitelist file`` (no ``pipe``);
* semi-trusted inputs get a forced ``-f`` chosen by a magic-byte sniff, never auto-detection;
* a caller string that looks like a joined command line is rejected.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMMON = ["-hide_banner", "-nostdin", "-loglevel", "error", "-protocol_whitelist", "file", "-y"]
PROBE_COMMON = ["-v", "error", "-hide_banner", "-protocol_whitelist", "file"]
MP4_FMT = "mov,mp4,m4a,3gp,3g2,mj2"
_FORBIDDEN_OPTS = frozenset(
    ("-protocol_blacklist", "-safe", "-allowed_extensions", "-allowed_segment_extensions")
    + ("-extension_picky", "-http_proxy", "-headers", "-user_agent")
)
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_JOINED = re.compile(r"^-[A-Za-z_:0-9]+\s+\S")  # e.g. "-i file" or "-vf scale=1:1" in one string


class FfError(RuntimeError):
    """An ffmpeg/ffprobe call failed or was refused before running."""


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
    rss_kb: int | None = None


def check_args(cmd: list[str]) -> None:
    """Refuse anything that is not a clean argument list."""
    if not cmd or not all(isinstance(a, str) for a in cmd):
        raise FfError("command must be a non-empty list of str")
    if re.search(r"\s", cmd[0]):
        raise FfError(f"executable contains whitespace (joined command line?): {cmd[0]!r}")
    for a in cmd[1:]:
        if _JOINED.match(a):
            raise FfError(f"argument looks like a joined command line: {a!r}")
        if re.match(r"^(\S*/)?(ffmpeg|ffprobe)\s", a):
            raise FfError(f"argument looks like a joined command line: {a!r}")
    name = Path(cmd[0]).name
    if "ffmpeg" in name and "-version" not in cmd and "-protocol_whitelist" not in cmd:
        raise FfError("ffmpeg call without -protocol_whitelist")
    if name in ("ffmpeg", "ffprobe") or "-protocol_whitelist" in cmd:
        _check_protocol_options(cmd)


def _check_protocol_options(cmd: list[str]) -> None:
    """Refuse caller-supplied protocol/demuxer-safety options and URL-style inputs (SEC-010/011).

    The only allowed whitelist is exactly one ``-protocol_whitelist file``; the options below
    widen what a hostile playlist may open and are never set by our templates.
    """
    wl = [i for i, a in enumerate(cmd) if a == "-protocol_whitelist"]
    if len(wl) > 1 or (wl and (wl[0] + 1 >= len(cmd) or cmd[wl[0] + 1] != "file")):
        raise FfError("protocol whitelist must be exactly one '-protocol_whitelist file'")
    for a in cmd[1:]:
        if a in _FORBIDDEN_OPTS:
            raise FfError(f"caller-supplied option refused: {a}")
    for i, a in enumerate(cmd[:-1]):
        if a == "-i" and _SCHEME.match(cmd[i + 1]) and not cmd[i + 1].startswith("file:"):
            raise FfError(f"URL-style input refused: {cmd[i + 1]!r}")


def ffmpeg_cmd(tools: Tools, *args: str) -> list[str]:
    return [tools.ffmpeg, *COMMON, *args]


def sniff_format(path: Path) -> str:
    """Forced demuxer name from the first bytes (ARCHITECTURE 11, F-17). Else FfError."""
    with path.open("rb") as fh:
        head = fh.read(16)
    if head[:3] == b"ID3" or (len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"fLaC":
        return "flac"
    if head[:4] == b"OggS":
        return "ogg"
    if head[4:8] == b"ftyp":
        return MP4_FMT
    raise FfError(f"unsupported_media: {path.name}")


def input_args(path: Path) -> list[str]:
    """``-f <forced> -i <path>`` for a semi-trusted or own file."""
    return ["-f", sniff_format(path), "-i", str(path)]


def run(
    cmd: list[str],
    timeout: float,
    *,
    check: bool = True,
    rss: bool = False,
) -> RunResult:
    """Run an argument list (never a shell). ``rss`` wraps with ``/usr/bin/time -v``."""
    check_args(cmd)
    full = cmd
    time_file: Path | None = None
    if rss:
        import tempfile

        fd = tempfile.NamedTemporaryFile(prefix="rss-", suffix=".txt", delete=False)  # noqa: SIM115
        fd.close()
        time_file = Path(fd.name)
        full = ["/usr/bin/time", "-v", "-o", str(time_file), *cmd]
    t = time.monotonic()
    try:
        p = subprocess.run(full, shell=False, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise FfError(f"timeout after {timeout}s: {cmd[0]}") from exc
    wall = time.monotonic() - t
    rss_kb: int | None = None
    if time_file is not None:
        m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", time_file.read_text())
        rss_kb = int(m.group(1)) if m else None
        time_file.unlink(missing_ok=True)
    res = RunResult(p.returncode, p.stdout, p.stderr.decode("utf-8", "replace"), wall, rss_kb)
    if check and p.returncode != 0:
        raise FfError(f"exit {p.returncode}: {' '.join(cmd[:6])}...\n{res.stderr[-2000:]}")
    return res


def probe_json(
    tools: Tools, path: Path, *extra: str, forced: str | None = None, timeout: float = 120
) -> dict[str, Any]:
    """ffprobe JSON with a forced ``-f`` (sniffed when not given)."""
    fmt = forced or sniff_format(path)
    cmd = [tools.ffprobe, *PROBE_COMMON, "-f", fmt, "-print_format", "json", *extra, str(path)]
    out = run(cmd, timeout).stdout
    data: dict[str, Any] = json.loads(out)
    return data


def version_line(binary: str) -> str:
    out = run([binary, "-version"], 30).stdout.decode().splitlines()
    return out[0] if out else ""
