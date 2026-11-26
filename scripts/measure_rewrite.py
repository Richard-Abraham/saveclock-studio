"""OQ-26: do SSE and a 100 MB upload stream without buffering? (plan 002 Step 7, Branch B)

Usage: python3 scripts/measure_rewrite.py [--web http://127.0.0.1:3000] [--api http://127.0.0.1:8000]
                                          [--container podman|docker]
Stdlib only. Measured 2026-11-26 on Next 16.4.6: SSE streams through the rewrite, but the rewrite
cuts request bodies at 10 MB, so Branch B applies (DECISIONS §8g): the browser sends the upload
straight to the API origin, with CORS allowing only the app origin. This script therefore checks

  1. the rewrite still works for ordinary calls (/health/live -> 200),
  2. SSE through the rewrite AND direct (progressive delivery),
  3. the CORS preflight from the app origin on the direct API origin (allowed) and from a foreign
     origin (not allowed),
  4. the 100 MB upload DIRECT to the API, sent as the browser would (Origin = app origin): status 200,
     exact byte count and sha256, the API saw data while the client was still sending, and the API
     container's memory grew by less than 40 MiB,
  5. for the record only: the same upload through the rewrite (expected to fail; not counted).

Prints a table and a final `OQ-26: PASS` or `OQ-26: FAIL (<reasons>)`; exit 0 / 1.
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
MEMORY_GROWTH_MAX = 40 * MIB
APP_ORIGIN = "http://localhost:3000"
# 1 MiB every 20 ms: on loopback 100 MB would otherwise be sent in a blink, and a ratio measured
# on a 0.1 s send says nothing. Paced, the whole send lasts at least ~2 s.
PACE_S = 0.02


def connect(base: str) -> http.client.HTTPConnection:
    parts = urlsplit(base)
    return http.client.HTTPConnection(parts.hostname, parts.port, timeout=120)


@dataclass
class Sse:
    ok: bool
    first_s: float
    max_gap_s: float
    progressive: int
    events: int
    note: str = ""


def measure_sse(base: str) -> Sse:
    conn = connect(base)
    path = f"/api/v1/_stub/sse?events={SSE_EVENTS}&interval_ms={SSE_INTERVAL_MS}"
    t0 = time.monotonic()
    conn.request("GET", path, headers={"Accept": "text/event-stream", "Origin": APP_ORIGIN})
    response = conn.getresponse()
    if response.status != 200:
        return Sse(False, 0, 0, 0, 0, f"status {response.status}")
    arrivals: list[float] = []
    while line := response.readline():
        if line.startswith(b"data:"):
            arrivals.append(time.monotonic() - t0)
    conn.close()
    if len(arrivals) < SSE_EVENTS:
        return Sse(False, arrivals[0] if arrivals else 0, 0, 0, len(arrivals), f"only {len(arrivals)} events")
    max_gap = max(b - a for a, b in zip(arrivals, arrivals[1:], strict=False))
    progressive = sum(1 for t in arrivals if arrivals[-1] - t > 0.5)  # delivered >0.5 s before the last
    ok = arrivals[0] <= SSE_FIRST_MAX_S and max_gap <= SSE_GAP_MAX_S and progressive >= SSE_PROGRESSIVE_MIN
    return Sse(ok, arrivals[0], max_gap, progressive, len(arrivals))


def container_id(container: str, service: str) -> str | None:
    project = os.environ.get("PROJECT", "saveclock")
    for label in ("io.podman.compose.project", "com.docker.compose.project"):
        out = subprocess.run(  # noqa: S603 - fixed argument list
            [container, "ps", "-q", "--filter", f"label={label}={project}", "--filter",
             f"label=com.docker.compose.service={service}"], capture_output=True, text=True, check=False
        )  # fmt: skip
        if out.stdout.split():
            return out.stdout.split()[0]
    return None


def memory_bytes(container: str, cid: str) -> int | None:
    """Current memory of the container: `stats --no-stream` (works rootless, no exec needed)."""
    out = subprocess.run(  # noqa: S603
        [container, "stats", "--no-stream", "--format", "{{.MemUsage}}", cid],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    usage = out.stdout.strip().split("/")[0].strip()  # e.g. "52.3MB / 512MB"
    for unit, factor in (("GiB", 1 << 30), ("MiB", MIB), ("KiB", 1 << 10), ("GB", 10**9), ("MB", 10**6), ("kB", 1000), ("B", 1)):
        if usage.endswith(unit):
            try:
                return int(float(usage[: -len(unit)]) * factor)
            except ValueError:
                return None
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
    memory_before: int | None
    memory_peak: int | None
    note: str = ""

    @property
    def growth(self) -> int | None:
        if self.memory_before is None or self.memory_peak is None:
            return None
        return max(0, self.memory_peak - self.memory_before)


def measure_upload(base: str, container: str, cid: str | None) -> Upload:
    rng = random.Random(26)  # seeded: the same 100 MB every run, never held in memory
    digest = hashlib.sha256()
    before = memory_bytes(container, cid) if cid else None
    peak = [before or 0]
    stop = threading.Event()

    def sampler() -> None:
        while not stop.is_set():
            value = memory_bytes(container, cid) if cid else None
            if value:
                peak[0] = max(peak[0], value)
            stop.wait(0.3)

    if cid:
        threading.Thread(target=sampler, daemon=True).start()
    conn = connect(base)
    conn.putrequest("POST", "/api/v1/_stub/upload-sink")
    conn.putheader("Content-Type", "application/octet-stream")
    conn.putheader("Content-Length", str(UPLOAD_BYTES))
    conn.putheader("Origin", APP_ORIGIN)
    conn.endheaders()
    start_wall = time.time()
    t0 = time.monotonic()
    try:
        for _ in range(UPLOAD_BYTES // MIB):
            chunk = rng.randbytes(MIB)
            digest.update(chunk)
            conn.send(chunk)
            time.sleep(PACE_S)
        send_s = time.monotonic() - t0
        response = conn.getresponse()
        body = response.read()
    except OSError as error:
        stop.set()
        return Upload(False, 0, time.monotonic() - t0, 0, 1, 0, False, before, peak[0], f"send failed: {error}")
    stop.set()
    conn.close()
    if response.status != 200:
        return Upload(False, response.status, send_s, 0, 1, 0, False, before, peak[0], f"status {response.status}")
    out = json.loads(body)
    first_after = out["first_chunk_at_ms"] / 1000 - start_wall
    ratio = first_after / send_s if send_s else 1.0
    hash_ok = out["sha256"] == digest.hexdigest()
    result = Upload(False, 200, send_s, first_after, ratio, out["bytes"], hash_ok, before, peak[0])
    result.ok = out["bytes"] == UPLOAD_BYTES and hash_ok and ratio < BUFFERED_RATIO_MAX
    return result


def preflight(base: str, origin: str) -> tuple[int, str | None]:
    conn = connect(base)
    conn.request("OPTIONS", "/api/v1/_stub/upload-sink", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-filename",
    })  # fmt: skip
    response = conn.getresponse()
    response.read()
    conn.close()
    return response.status, response.getheader("access-control-allow-origin")


def mib(value: int | None) -> str:
    return "n/a" if value is None else f"{value / MIB:.1f} MiB"


def describe_sse(label: str, r: Sse) -> str:
    return (
        f"{label:<30} SSE     {'PASS' if r.ok else 'FAIL'}  first event {r.first_s:.2f} s (<= {SSE_FIRST_MAX_S}), "
        f"max gap {r.max_gap_s:.2f} s (<= {SSE_GAP_MAX_S}), {r.progressive}/{r.events} delivered "
        f"progressively (>= {SSE_PROGRESSIVE_MIN}) {r.note}"
    )


def describe_upload(label: str, r: Upload, verdict: str | None = None) -> str:
    return (
        f"{label:<30} UPLOAD  {verdict or ('PASS' if r.ok else 'FAIL')}  status {r.status}, {r.bytes_seen} bytes "
        f"(want {UPLOAD_BYTES}), sha256 {'match' if r.hash_ok else 'MISMATCH'}, send {r.send_s:.2f} s, API saw the "
        f"first chunk {r.first_chunk_after_s:.2f} s after the send began (ratio {r.ratio:.2f}, want < "
        f"{BUFFERED_RATIO_MAX}), memory {mib(r.memory_before)} -> peak {mib(r.memory_peak)} (growth "
        f"{mib(r.growth)}, want < {MEMORY_GROWTH_MAX // MIB} MiB) {r.note}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://127.0.0.1:3000")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--container", default=(shutil.which("docker") and "docker") or "podman")
    args = parser.parse_args()
    reasons: list[str] = []

    conn = connect(args.web)
    conn.request("GET", "/api/v1/health/live")
    status = conn.getresponse().status
    conn.close()
    print(f"{'rewrite (ordinary calls)':<30} GET /api/v1/health/live through :3000 -> {status}")
    if status != 200:
        reasons.append(f"item 1: the rewrite answered {status} for /health/live")

    for label, base in (("through the rewrite", args.web), ("direct to the API", args.api)):
        sse = measure_sse(base)
        print(describe_sse(label, sse))
        if not sse.ok:
            reasons.append(
                f"SSE {label}: first {sse.first_s:.2f} s, max gap {sse.max_gap_s:.2f} s, "
                f"{sse.progressive}/{sse.events} progressive {sse.note}".strip()
            )

    ok_status, ok_origin = preflight(args.api, APP_ORIGIN)
    bad_status, bad_origin = preflight(args.api, "http://evil.example")
    cors_ok = ok_origin == APP_ORIGIN and bad_origin is None
    print(
        f"{'CORS preflight (direct)':<30} CORS    {'PASS' if cors_ok else 'FAIL'}  from {APP_ORIGIN} -> "
        f"{ok_status} allow-origin={ok_origin}; from http://evil.example -> {bad_status} allow-origin={bad_origin}"
    )
    if not cors_ok:
        reasons.append(f"CORS: app origin got {ok_origin!r}, foreign origin got {bad_origin!r}")

    api_cid = container_id(args.container, "api")
    web_cid = container_id(args.container, "web")
    if api_cid is None:
        print("note: api container not found; memory growth cannot be measured")
    up = measure_upload(args.api, args.container, api_cid)
    memory_ok = up.growth is not None and up.growth < MEMORY_GROWTH_MAX
    print(describe_upload("direct to the API (Branch B)", up, "PASS" if up.ok and memory_ok else "FAIL"))
    if not up.ok:
        reasons.append(
            f"upload direct: status {up.status}, bytes {up.bytes_seen}, hash {'ok' if up.hash_ok else 'MISMATCH'}, "
            f"ratio {up.ratio:.2f} {up.note}".strip()
        )
    if not memory_ok:
        reasons.append(f"upload direct: API memory growth {mib(up.growth)} (want < {MEMORY_GROWTH_MAX // MIB} MiB)")

    info = measure_upload(args.web, args.container, web_cid)
    print(describe_upload("through the rewrite (info)", info, "INFO"))

    if reasons:
        print("OQ-26: FAIL (" + "; ".join(reasons) + ")")
        return 1
    print("OQ-26: PASS (Branch B: upload direct to the API; the rewrite carries ordinary calls and SSE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
