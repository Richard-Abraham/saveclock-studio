"""OQ-26: do SSE and a 100 MB upload stream through the Next.js rewrite without buffering?

Usage: python3 scripts/measure_rewrite.py [--web http://127.0.0.1:3000] [--api http://127.0.0.1:8000]
                                          [--container podman|docker] [--direct]
Stdlib only. Measures through the web origin, then repeats directly on the API as the control (the
control must pass, otherwise the stub routes are wrong, not the proxy). Prints a table and a final
`OQ-26: PASS` or `OQ-26: FAIL (<reasons>)`; exit 0 / 1. With --direct only the control runs.
"""

import argparse
import hashlib
import http.client
import json
import os
import random
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

MIB = 1 << 20
UPLOAD_BYTES = 100 * MIB
SSE_EVENTS = 30
SSE_INTERVAL_MS = 1000
SSE_FIRST_MAX_S = 2.0
SSE_GAP_MAX_S = 2.0
SSE_PROGRESSIVE_MIN = 25
BUFFERED_RATIO_MAX = 0.5
WEB_MEMORY_GROWTH_MAX = 40 * MIB
# 1 MiB every 20 ms: on loopback 100 MB would otherwise be sent in a blink, and a ratio measured
# on a 0.1 s send says nothing. Paced, the whole send lasts at least ~2 s.
PACE_S = 0.02


@dataclass
class Sse:
    ok: bool
    first_s: float
    max_gap_s: float
    progressive: int
    events: int
    note: str = ""


def connect(base: str) -> http.client.HTTPConnection:
    parts = urlsplit(base)
    return http.client.HTTPConnection(parts.hostname, parts.port, timeout=120)


def measure_sse(base: str) -> Sse:
    conn = connect(base)
    path = f"/api/v1/_stub/sse?events={SSE_EVENTS}&interval_ms={SSE_INTERVAL_MS}"
    t0 = time.monotonic()
    conn.request("GET", path, headers={"Accept": "text/event-stream"})
    response = conn.getresponse()
    if response.status != 200:
        return Sse(False, 0, 0, 0, 0, f"status {response.status}")
    arrivals: list[float] = []
    while True:
        line = response.readline()
        if not line:
            break
        if line.startswith(b"data:"):
            arrivals.append(time.monotonic() - t0)
    conn.close()
    if len(arrivals) < SSE_EVENTS:
        return Sse(False, arrivals[0] if arrivals else 0, 0, 0, len(arrivals), f"only {len(arrivals)} events")
    gaps = [b - a for a, b in zip(arrivals, arrivals[1:], strict=False)]
    # events that were already delivered more than 0.5 s before the final one arrived
    progressive = sum(1 for t in arrivals if arrivals[-1] - t > 0.5)
    first, max_gap = arrivals[0], max(gaps)
    ok = first <= SSE_FIRST_MAX_S and max_gap <= SSE_GAP_MAX_S and progressive >= SSE_PROGRESSIVE_MIN
    return Sse(ok, first, max_gap, progressive, len(arrivals))


def cgroup_read(container: str, name: str, file: str) -> int | None:
    out = subprocess.run(  # noqa: S603 - fixed argument list
        [container, "exec", name, "cat", f"/sys/fs/cgroup/{file}"], capture_output=True, text=True, check=False
    )
    try:
        return int(out.stdout.strip())
    except ValueError:
        return None


def web_container(container: str) -> str | None:
    for project_label in ("io.podman.compose.project", "com.docker.compose.project"):
        out = subprocess.run(  # noqa: S603
            [container, "ps", "-q", "--filter", f"label={project_label}={os.environ.get('PROJECT', 'saveclock')}", "--filter",
             "label=com.docker.compose.service=web"], capture_output=True, text=True, check=False
        )  # fmt: skip
        ids = out.stdout.split()
        if ids:
            return ids[0]
    return None


@dataclass
class Upload:
    ok: bool
    status: int
    send_s: float
    first_chunk_after_s: float
    ratio: float
    bytes_seen: int
    hash_ok: bool
    memory_growth: int | None
    note: str = ""


def measure_upload(base: str, container: str | None, name: str | None) -> Upload:
    rng = random.Random(26)  # seeded: the same 100 MB every run, never held in memory
    digest = hashlib.sha256()
    baseline_peak = cgroup_read(container, name, "memory.peak") if container and name else None
    baseline_cur = cgroup_read(container, name, "memory.current") if container and name else None
    max_cur = [baseline_cur or 0]
    stop = threading.Event()

    def sampler() -> None:
        while not stop.is_set():
            value = cgroup_read(container, name, "memory.current") if container and name else None
            if value:
                max_cur[0] = max(max_cur[0], value)
            stop.wait(0.5)

    if container and name:
        threading.Thread(target=sampler, daemon=True).start()

    conn = connect(base)
    conn.putrequest("POST", "/api/v1/_stub/upload-sink")
    conn.putheader("Content-Type", "application/octet-stream")
    conn.putheader("Content-Length", str(UPLOAD_BYTES))
    conn.putheader("Origin", "http://localhost:3000")
    conn.endheaders()
    start_wall = time.time()
    t0 = time.monotonic()
    try:
        for _ in range(UPLOAD_BYTES // MIB):
            chunk = rng.randbytes(MIB)
            digest.update(chunk)
            conn.send(chunk)
            time.sleep(PACE_S)
    except OSError as error:
        stop.set()
        return Upload(False, 0, time.monotonic() - t0, 0, 0, 0, False, None, f"send failed: {error}")
    send_s = time.monotonic() - t0
    response = conn.getresponse()
    body = response.read()
    stop.set()
    conn.close()
    if response.status != 200:
        return Upload(False, response.status, send_s, 0, 0, 0, False, None, f"status {response.status}")
    out = json.loads(body)
    first_after = out["first_chunk_at_ms"] / 1000 - start_wall
    ratio = first_after / send_s if send_s else 1.0
    peak = cgroup_read(container, name, "memory.peak") if container and name else None
    growth = None
    if baseline_peak is not None and peak is not None:
        growth = max(peak - baseline_peak, max_cur[0] - (baseline_cur or 0))
    hash_ok = out["sha256"] == digest.hexdigest()
    ok = out["bytes"] == UPLOAD_BYTES and hash_ok and ratio < BUFFERED_RATIO_MAX
    if growth is not None and name:
        ok = ok and growth < WEB_MEMORY_GROWTH_MAX
    return Upload(ok, 200, send_s, first_after, ratio, out["bytes"], hash_ok, growth)


def describe_sse(label: str, r: Sse) -> str:
    return (
        f"{label:<26} SSE    {'PASS' if r.ok else 'FAIL'}  first event {r.first_s:.2f} s (<= {SSE_FIRST_MAX_S}), "
        f"max gap {r.max_gap_s:.2f} s (<= {SSE_GAP_MAX_S}), {r.progressive}/{r.events} delivered progressively "
        f"(>= {SSE_PROGRESSIVE_MIN}) {r.note}"
    )


def describe_upload(label: str, r: Upload) -> str:
    memory = "n/a" if r.memory_growth is None else f"{r.memory_growth / MIB:.1f} MiB (< {WEB_MEMORY_GROWTH_MAX // MIB})"
    return (
        f"{label:<26} UPLOAD {'PASS' if r.ok else 'FAIL'}  status {r.status}, {r.bytes_seen} bytes "
        f"(want {UPLOAD_BYTES}), sha256 {'match' if r.hash_ok else 'MISMATCH'}, send {r.send_s:.2f} s, "
        f"API saw the first chunk {r.first_chunk_after_s:.2f} s after the send began "
        f"(ratio {r.ratio:.2f}, want < {BUFFERED_RATIO_MAX}), web memory growth {memory} {r.note}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://127.0.0.1:3000")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--container", default=shutil.which("docker") and "docker" or "podman")
    parser.add_argument("--direct", action="store_true", help="measure only the direct API origin")
    args = parser.parse_args()
    reasons: list[str] = []

    if not args.direct:
        conn = connect(args.web)
        conn.request("GET", "/api/v1/health/live")
        host_status = conn.getresponse().status
        conn.close()
        print(f"{'rewrite: Host seen by the API':<26} GET /api/v1/health/live through :3000 -> {host_status}")
        if host_status != 200:
            reasons.append(f"item 1: the rewrite answered {host_status} for /health/live")

    controls: list[str] = []
    control_sse = measure_sse(args.api)
    print(describe_sse("control (direct API)", control_sse))
    control_up = measure_upload(args.api, None, None)
    print(describe_upload("control (direct API)", control_up))
    if not control_sse.ok:
        controls.append("control SSE failed: the API stub is wrong, not the proxy")
    if not control_up.ok:
        controls.append("control upload failed: the API stub is wrong, not the proxy")

    if not args.direct:
        cid = web_container(args.container)
        if cid is None:
            print("note: web container not found; memory growth is not measured")
        sse = measure_sse(args.web)
        print(describe_sse("through the rewrite", sse))
        if not sse.ok:
            reasons.append(
                f"item 2 SSE: first {sse.first_s:.2f} s, max gap {sse.max_gap_s:.2f} s, "
                f"{sse.progressive}/{sse.events} progressive {sse.note}".strip()
            )
        up = measure_upload(args.web, args.container, cid)
        print(describe_upload("through the rewrite", up))
        if not up.ok:
            reasons.append(
                f"item 3 upload: status {up.status}, bytes {up.bytes_seen}, hash {'ok' if up.hash_ok else 'MISMATCH'}, "
                f"ratio {up.ratio:.2f}, memory growth {up.memory_growth} {up.note}".strip()
            )

    reasons = controls + reasons
    if reasons:
        print("OQ-26: FAIL (" + "; ".join(reasons) + ")")
        return 1
    print("OQ-26: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
