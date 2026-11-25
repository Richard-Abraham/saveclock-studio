"""Hostile-input hardening test (G0-25, F-17; ARCHITECTURE 11.3, SEC-010/011).

``python -I -m spike.hostile --ffmpeg <path> [--ffprobe <path>]``

Inputs are text files WE generate under ``data/synth/hostile/``. A throwaway listener bound to
127.0.0.1 (ephemeral port) records connections. ``/etc/passwd`` / ``/etc/hostname`` are referenced
only to prove they are NOT read: output is scanned for a short token and only a boolean is kept;
file contents are never printed or stored.

Layers per hostile file (every one must record zero connections and leak nothing):
  L1 production template (whitelist ``file`` + forced ``-f``) for ffprobe and ffmpeg;
  L2 whitelist only (auto-detect demuxer)           -> shows the whitelist alone blocks network;
  L3 forced ``-f`` only (no whitelist)              -> shows the forced demuxer alone blocks it.
Plus the magic-byte sniff (a/b/c rejected as ``unsupported_media``), the wrapper's refusal of
caller-supplied protocol options, and a negative control (no whitelist, no ``-f``) that SHOULD hit
the listener, proving the detector works. Exit 1 on any hardened leak; a control that does not hit
is reported but is not a leak.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import socketserver
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from spike.ffwrap import MP4_FMT, FfError, Tools, check_args, ffmpeg_cmd, run, sniff_format

HOME = Path.home() / "saveclock-spike"
WHITELIST = ["-protocol_whitelist", "file"]
ALLOWED_FORMATS = {"mp3", "wav", "flac", "ogg", "mov", "mp4", "m4a", "3gp", "3g2", "mj2"}
PROTO_ATTEMPT = re.compile(r"not on whitelist|hls|applehttp|concat", re.IGNORECASE)
LEAK_TOKENS = ("root:x:",)  # short distinctive /etc/passwd token; only a boolean is kept
TIMEOUT = 60


class Listener:
    """Records inbound TCP connections on 127.0.0.1 (ephemeral port)."""

    def __init__(self) -> None:
        self.count = 0
        outer = self

        class H(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                outer.count += 1
                try:
                    self.request.settimeout(0.5)
                    self.request.recv(1024)
                    self.request.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                except OSError:
                    pass

        self.srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        self.srv.daemon_threads = True
        self.port: int = self.srv.server_address[1]
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.t.start()

    def close(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()


@dataclass
class Case:
    name: str
    path: Path
    fmt: str  # demuxer a (wrong) caller might force by extension
    note: str


def make_inputs(d: Path, port: int, control_wav: Path, tools: Tools) -> list[Case]:
    d.mkdir(parents=True, exist_ok=True)
    seg = f"http://127.0.0.1:{port}/x.ts"
    hls = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:1\n#EXTINF:1.0,\n{}\n#EXT-X-ENDLIST\n"
    files = {
        "evil_hls_http.mp3": hls.format(seg),
        "evil_hls_file.mp3": hls.format("file:///etc/passwd"),
        "evil_concat.mp3": "ffconcat version 1.0\nfile '/etc/hostname'\n",
        "evil_concat_http.mp3": f"ffconcat version 1.0\nfile '{seg}'\n",
        "evil.m4a": "ffconcat version 1.0\nfile '/etc/passwd'\n",
    }
    for n, body in files.items():
        (d / n).write_text(body, encoding="ascii")
    ctl = d / "control.mp3"
    if not ctl.exists():
        cmd = ffmpeg_cmd(
            tools, "-f", "wav", "-i", str(control_wav), "-t", "2", "-c:a", "libmp3lame", str(ctl)
        )
        run(cmd, 120)
    cases = [Case(n, d / n, MP4_FMT if n.endswith(".m4a") else "mp3", "hostile") for n in files]
    cases.append(Case("control.mp3", ctl, "mp3", "control"))
    return cases


def _raw(cmd: list[str]) -> tuple[int, str]:
    """Deliberately NOT ffwrap.run: the negative control and layer tests must be able to run
    templates the wrapper refuses. shell=False, timeout, output returned for token scanning only."""
    try:
        p = subprocess.run(cmd, shell=False, capture_output=True, timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def probe_cmd(tools: Tools, c: Case, whitelist: bool, forced: bool) -> list[str]:
    cmd = [tools.ffprobe, "-v", "error", "-hide_banner"]
    if whitelist:
        cmd += WHITELIST
    if forced:
        cmd += ["-f", c.fmt]
    return [*cmd, "-print_format", "json", "-show_format", "-show_streams", str(c.path)]


def ffmpeg_decode_cmd(tools: Tools, c: Case, whitelist: bool, forced: bool) -> list[str]:
    cmd = [tools.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error"]
    if whitelist:
        cmd += WHITELIST
    if forced:
        cmd += ["-f", c.fmt]
    return [*cmd, "-i", str(c.path), "-f", "null", "-"]


@dataclass
class Result:
    label: str
    case: str
    rc: int
    conns: int
    leaked: bool
    streams: int = 0
    fmt: str = ""
    attempted: bool = False
    ok: bool = True
    why: str = ""
    extra: dict[str, object] = field(default_factory=dict)


def execute(lst: Listener, cmd: list[str], label: str, case: Case) -> Result:
    before = lst.count
    rc, out = _raw(cmd)
    time.sleep(0.25)  # let a straggling connection land
    for tok in (str(case.path), case.path.name):
        out = out.replace(tok, "<f>")  # file names contain 'hls'/'concat'; not evidence
    host = socket.gethostname()
    leaked = any(t in out for t in LEAK_TOKENS) or (len(host) >= 4 and host in out)
    streams, fmt = 0, ""
    if cmd[0].endswith("ffprobe") and "{" in out:
        try:
            j = json.loads(out[out.index("{") :])
            streams = len(j.get("streams", []))
            fmt = str(j.get("format", {}).get("format_name", ""))
        except (ValueError, json.JSONDecodeError):
            pass
    return Result(
        label,
        case.name,
        rc,
        lst.count - before,
        leaked,
        streams,
        fmt,
        bool(PROTO_ATTEMPT.search(out)),
    )


def wrapper_rejections() -> list[tuple[str, bool]]:
    """The wrapper must refuse caller-supplied protocol options (SEC-010/011)."""
    base = ["/usr/bin/ffmpeg", "-protocol_whitelist", "file"]
    bad: dict[str, list[str]] = {
        "no whitelist": ["/usr/bin/ffmpeg", "-i", "a.mp4"],
        "second -protocol_whitelist file,http": [
            *base,
            "-protocol_whitelist",
            "file,http",
            "-i",
            "a",
        ],
        "whitelist widened to file,http": ["/usr/bin/ffmpeg", "-protocol_whitelist", "file,http"],
        "-protocol_blacklist caller option": [*base, "-protocol_blacklist", "none", "-i", "a"],
        "-safe 0 (concat)": [*base, "-safe", "0", "-i", "a"],
        "-allowed_extensions ALL": [*base, "-allowed_extensions", "ALL", "-i", "a"],
        "-i http URL": [*base, "-i", "http://127.0.0.1:1/x"],
        "-i concat: URL": [*base, "-i", "concat:a|b"],
        "joined command string": [*base, "-i a.mp4"],
        "ffprobe widened whitelist": ["/usr/bin/ffprobe", "-protocol_whitelist", "file,http", "x"],
    }
    out: list[tuple[str, bool]] = []
    for name, cmd in bad.items():
        try:
            check_args(cmd)
            out.append((name, False))
        except FfError:
            out.append((name, True))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ffmpeg", required=True)
    ap.add_argument("--ffprobe", default=None)
    ap.add_argument("--dir", type=Path, default=HOME / "data/synth/hostile")
    ap.add_argument("--wav", type=Path, default=HOME / "data/synth/click_128_30s.wav")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    ffmpeg = str(Path(a.ffmpeg).resolve())
    ffprobe = a.ffprobe or str(Path(ffmpeg).with_name("ffprobe"))
    tools = Tools(ffmpeg, ffprobe)
    print(f"ffmpeg: {run([ffmpeg, '-version'], 30).stdout.decode().splitlines()[0]}")

    lst = Listener()
    print(f"listener: 127.0.0.1:{lst.port} (ephemeral)")
    results: list[Result] = []
    plan_hits = nc_hits = 0
    problems: list[str] = []
    try:
        cases = make_inputs(a.dir, lst.port, a.wav, tools)
        hostile = [c for c in cases if c.note == "hostile"]
        control = next(c for c in cases if c.note == "control")

        # 1. magic-byte sniff
        for c in hostile:
            try:
                sniff_format(c.path)
                problems.append(f"sniff accepted {c.name}")
                print(f"sniff {c.name}: ACCEPTED (BAD)")
            except FfError as e:
                ok = str(e).startswith("unsupported_media")
                print(
                    f"sniff {c.name}: rejected unsupported_media" if ok else f"sniff {c.name}: {e}"
                )
                if not ok:
                    problems.append(f"sniff wrong error {c.name}")
        cf = sniff_format(control.path)
        print(f"sniff {control.name}: {cf}")
        if cf != "mp3":
            problems.append("control mp3 not sniffed as mp3")

        # 2. layered runs
        layers = (
            ("L1 prod ffprobe", True, True, "probe"),
            ("L1 prod ffmpeg", True, True, "ffmpeg"),
            ("L2 whitelist-only ffprobe", True, False, "probe"),
            ("L2 whitelist-only ffmpeg", True, False, "ffmpeg"),
            ("L3 forced-f-only ffprobe", False, True, "probe"),
            ("L3 forced-f-only ffmpeg", False, True, "ffmpeg"),
        )
        for c in hostile:
            for label, wl, fo, tool in layers:
                cmd = (probe_cmd if tool == "probe" else ffmpeg_decode_cmd)(tools, c, wl, fo)
                r = execute(lst, cmd, label, c)
                r.ok = r.conns == 0 and not r.leaked
                if not r.ok:
                    r.why = f"conns={r.conns} leaked={r.leaked}"
                if label.startswith("L1"):
                    if r.rc == 0 and r.streams > 0:
                        r.ok, r.why = False, r.why + " parsed streams"
                    if r.attempted:
                        r.ok, r.why = False, r.why + " hls/concat/whitelist hit in output"
                    if r.fmt and not (set(r.fmt.split(",")) & ALLOWED_FORMATS):
                        r.ok, r.why = False, r.why + f" format {r.fmt}"
                results.append(r)
                if not r.ok:
                    problems.append(f"{label} {c.name}: {r.why}")
        # 3. control file still works under the production template
        r = execute(lst, probe_cmd(tools, control, True, True), "L1 control ffprobe", control)
        ctl_ok = r.rc == 0 and r.streams >= 1
        print(
            f"control.mp3 under production template: {'OK' if ctl_ok else 'FAIL'} "
            f"(rc={r.rc}, streams={r.streams}, format={r.fmt})"
        )
        if not ctl_ok:
            problems.append("control mp3 does not probe under production template")

        # 3b. behavioural proof the explicit whitelist is really on the command line: without it
        # ffprobe logs "Setting default whitelist" (the implicit local-file default).
        wcmd = probe_cmd(tools, control, True, True)
        wcmd[1:3] = ["-v", "debug"]
        _, wout = _raw(wcmd)
        wl_active = "default whitelist" not in wout.lower()
        print(f"explicit -protocol_whitelist active in production template: {wl_active}")
        if not wl_active:
            problems.append("production template runs without an explicit -protocol_whitelist")

        # 4. wrapper rejects caller-supplied protocol options
        wr = wrapper_rejections()
        for name, ok in wr:
            print(f"wrapper reject [{name}]: {'rejected' if ok else 'ACCEPTED (BAD)'}")
            if not ok:
                problems.append(f"wrapper accepted: {name}")

        # 5. negative control: no whitelist, no forced -f (the plan's control), plus variants that
        # progressively weaken the defaults so the listener proves it can see a leak.
        print("negative control (NO whitelist, NO forced -f, plus weakened variants):")
        perm = ["-protocol_whitelist", "file,http,https,tcp"]
        for c in hostile:
            m3u8 = a.dir / (c.path.stem + ".as_m3u8.m3u8")
            m3u8.write_bytes(c.path.read_bytes())
            variants: list[tuple[str, Case, list[str]]] = [
                ("plan: auto-detect, no flags", c, []),
                ("auto-detect, .m3u8 name", Case(m3u8.name, m3u8, c.fmt, "nc"), []),
                ("forced -f hls, no whitelist arg", c, ["-f", "hls"]),
                ("forced -f hls + whitelist file,http,tcp", c, [*perm, "-f", "hls"]),
                (
                    "forced -f concat -safe 0 + whitelist file,http,tcp",
                    c,
                    [*perm, "-f", "concat", "-safe", "0"],
                ),
            ]
            for vname, vc, pre in variants:
                for tool in ("ffprobe", "ffmpeg"):
                    if tool == "ffprobe":
                        cmd = [
                            tools.ffprobe,
                            "-v",
                            "error",
                            "-hide_banner",
                            *pre,
                            "-show_format",
                            str(vc.path),
                        ]
                    else:
                        cmd = [
                            tools.ffmpeg,
                            "-hide_banner",
                            "-nostdin",
                            "-loglevel",
                            "error",
                            *pre,
                            "-i",
                            str(vc.path),
                            "-f",
                            "null",
                            "-",
                        ]
                    rr = execute(lst, cmd, f"NC {tool} {vname}", vc)
                    nc_hits += rr.conns
                    if vname.startswith("plan:"):
                        plan_hits += rr.conns
                    results.append(rr)
                    print(
                        f"  NC {c.name:22} [{vname}] {tool:7} rc={rr.rc:<3} "
                        f"connections={rr.conns} content_leak={rr.leaked}"
                    )
        # a content leak in the control is expected-to-be-possible, but under hardened flags it is not
    finally:
        lst.close()

    hard = [r for r in results if not r.label.startswith("NC")]
    hard_conns = sum(r.conns for r in hard)
    hard_leaks = sum(1 for r in hard if r.leaked)
    for r in hard:
        print(
            f"  {r.label:26} {r.case:22} rc={r.rc:<3} conns={r.conns} streams={r.streams} "
            f"fmt={r.fmt or '-'} {'ok' if r.ok else 'FAIL ' + r.why}"
        )
    nc_leaks = sum(1 for r in results if r.label.startswith("NC") and r.leaked)
    print(
        f"negative control: plan control (no whitelist arg, no -f) = {plan_hits} connection(s); "
        f"all weakened variants = {nc_hits}; content_leak_cases={nc_leaks}"
    )
    if plan_hits == 0:
        print(
            "negative control: the plan's exact control did NOT hit (default local-file whitelist "
            "'file,crypto,data' and the demuxer extension checks block it); only variants with an "
            "explicit permissive whitelist hit"
        )
    if nc_hits == 0:
        print(
            "negative control: DID NOT HIT the listener on this build (leak detection NOT proven "
            "by the control; hardened layers still recorded 0)"
        )
    else:
        print("negative control: listener hit (the detector works)")
    if hard_leaks:
        print("SECURITY FINDING: hostile content leaked under hardened flags")
    if problems or hard_conns:
        print("G0-25 FAIL (" + f"{hard_conns} connections; " + "; ".join(problems[:8]) + ")")
        return 1
    print(f"G0-25 PASS ({hard_conns} connections)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
